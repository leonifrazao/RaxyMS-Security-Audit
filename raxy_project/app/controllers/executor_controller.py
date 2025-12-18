"""Endpoints para orquestrar execuções em lote."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from app.dependencies import (
    get_account_repository,
    get_database_repository,
    get_executor_service,
    get_logging_service,
)
from app.schemas import (
    AccountPayload,
    AccountSource,
    ExecutorBatchRequest,
    ExecutorBatchResponse,
)
from app.core import BaseController
from raxy.domain import Conta
from raxy.interfaces.repositories import IContaRepository, IDatabaseRepository
from raxy.interfaces.services import IExecutorEmLoteService, ILoggingService
from app.dependencies import get_executor_service, get_task_queue
from rq import Queue


class ExecutorController(BaseController):
    """Controller para execução em lote."""
    
    def __init__(self):
        super().__init__()
        self.router = APIRouter(prefix="/executor", tags=["Executor"])
        self._register_routes()
    
    def _register_routes(self):
        """Registra as rotas do controller."""
        self.router.add_api_route(
            "/run",
            self.run_executor,
            methods=["POST"],
            response_model=ExecutorBatchResponse
        )


    @staticmethod
    def _executar_batch(
        executor: IExecutorEmLoteService,
        logger: ILoggingService,
        acoes: list[str],
        contas: list[Conta] | None,
        source: AccountSource,
    ) -> None:
        """Wrapper para permitir logging padronizado em tarefas assíncronas."""
        logger.info(
            "Execução em lote disparada via API",
            acoes=acoes,
            origem=source.value,
            contas=len(contas) if contas else None,
        )
        executor.executar(acoes, contas)
        logger.sucesso("Execução em lote concluída via API", origem=source.value)


    def run_executor(
        self,
        payload: ExecutorBatchRequest,
        background_tasks: BackgroundTasks,
        executor_service: IExecutorEmLoteService = Depends(get_executor_service),
        logger: ILoggingService = Depends(get_logging_service),
        conta_repository: IContaRepository = Depends(get_account_repository),
        database_repository: IDatabaseRepository = Depends(get_database_repository),
    ) -> ExecutorBatchResponse:
        """Registra uma execução em lote para ser processada em segundo plano."""
        self.log_request("run_executor", {
            "actions": payload.actions,
            "source": payload.source.value if payload.source else "file"
        })
        
        try:
            contas_manual = self._build_manual_accounts(payload.manual_accounts())
            source = self._determine_source(payload, contas_manual)
            
            if source is AccountSource.DATABASE:
                if database_repository is None:
                    logger.aviso("Database repository não configurado")
                    contas_para_executar = []
                else:
                    contas_para_executar = self._build_database_accounts(database_repository, logger)
            elif contas_manual:
                contas_para_executar = contas_manual
            else:
                contas_para_executar = conta_repository.listar()
            
            background_tasks.add_task(
                self._executar_batch,
                executor_service,
                logger,
                payload.actions,
                contas_para_executar,
                source,
            )
            
            response = ExecutorBatchResponse(
                status="scheduled",
                detail="Execução em lote iniciada em background",
                source=source,
            )
            self.log_response("run_executor", {"source": source.value})
            return response
        except Exception as e:
            self.handle_service_error(e, "run_executor")


    @staticmethod
    def _determine_source(
        payload: ExecutorBatchRequest, contas_manual: list[Conta]
    ) -> AccountSource:
        """Determina a origem das contas."""
        if contas_manual:
            return AccountSource.MANUAL
        if payload.source is AccountSource.DATABASE:
            return AccountSource.DATABASE
        return AccountSource.FILE
    
    @staticmethod
    def _build_manual_accounts(contas_payload: list[AccountPayload]) -> list[Conta]:
        """Constrói lista de contas a partir do payload."""
        contas: list[Conta] = []
        for item in contas_payload:
            perfil = item.profile_id or item.email
            contas.append(Conta(
                email=item.email,
                senha=item.password,
                id_perfil=perfil
            ))
        return contas
    
    @staticmethod
    def _build_database_accounts(
        database_repository: IDatabaseRepository,
        logger: ILoggingService,
    ) -> list[Conta]:
        """Constrói lista de contas a partir do banco de dados."""
        registros = database_repository.listar_contas()
        contas: list[Conta] = []
        
        for registro in registros:
            if not isinstance(registro, dict):
                continue
            
            email = registro.get("email")
            senha = registro.get("senha") or registro.get("password") or ""
            
            if not email or not senha:
                logger.aviso(
                    "Registro de conta inválido ao executar via banco de dados.",
                    registro=str(registro)[:200],
                )
                continue
            
            perfil = (
                registro.get("id_perfil")
                or registro.get("perfil")
                or registro.get("profile_id")
                or email
            )
            
            contas.append(Conta(
                email=email,
                senha=senha,
                id_perfil=perfil
            ))
        
        return contas


# Cria instância do controller e exporta o router
controller = ExecutorController()
router = controller.router

__all__ = ["router", "ExecutorController"]


@router.post("/job/start")
def start_job(
    request: Request,
    payload: ExecutorBatchRequest,
    queue: Queue = Depends(get_task_queue),
):
    """
    Inicia uma execução em lote em background (Worker).
    """
    from app.tasks import run_farm_task
    from fastapi import Request
    
    # Por enquanto, suporta apenas uma conta por job para simplificar o rastreamento
    contas = payload.manual_accounts()
    if not contas or len(contas) != 1:
        raise HTTPException(status_code=400, detail="Para jobs em background, envie exatamente uma conta em manual_accounts.")
        
    email = contas[0].email
    
    job = queue.enqueue(
        run_farm_task,
        args=(email, payload.actions),
        job_timeout='20m',
        result_ttl=3600
    )
    
    return {
        "job_id": job.get_id(),
        "status": "queued",
        "message": f"Job iniciado para {email}"
    }


@router.get("/job/status/{job_id}")
def get_job_status(
    job_id: str,
    queue: Queue = Depends(get_task_queue),
):
    """
    Verifica o status de um job.
    """
    from rq.job import Job
    from rq.exceptions import NoSuchJobError
    
    try:
        job = Job.fetch(job_id, connection=queue.connection)
    except NoSuchJobError:
        raise HTTPException(status_code=404, detail="Job não encontrado")
        
    return {
        "job_id": job.get_id(),
        "status": job.get_status(),
        "result": job.result,
        "enqueued_at": job.enqueued_at,
        "started_at": job.started_at,
        "ended_at": job.ended_at,
        "meta": job.meta
    }