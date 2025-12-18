"""Endpoints para executor em lote."""

from __future__ import annotations
from typing import Optional, List
from fastapi import APIRouter, Request

from raxy.infrastructure.logging import get_logger
from raxy.infrastructure.config.config import get_config
from raxy.adapters.http.schemas import (
    ExecutorRequest,
    ExecutorResponse,
    JobStatusResponse,
)

router = APIRouter(prefix="/executor", tags=["Executor"])
logger = get_logger()


@router.post("/run", response_model=ExecutorResponse)
def run_executor(request: ExecutorRequest) -> ExecutorResponse:
    """Executa o farm para as contas especificadas."""
    from raxy.core.services.executor_service import ExecutorEmLote
    from raxy.adapters.api.rewards_data_api import RewardsDataAPI
    from raxy.adapters.api.bing_suggestion_api import BingSuggestionAPI
    from raxy.core.services.bingflyout_service import BingFlyoutService
    from raxy.adapters.api.mail_tm_api import MailTm
    from raxy.adapters.repositories.file_account_repository import ArquivoContaRepository
    from raxy.infrastructure.manager import ProxyManager
    
    config = get_config()
    
    try:
        executor = ExecutorEmLote(
            rewards_service=RewardsDataAPI(logger=logger),
            bing_search_service=BingSuggestionAPI(logger=logger),
            bing_flyout_service=BingFlyoutService(logger=logger),
            proxy_manager=ProxyManager(sources=config.proxy.sources, use_console=False),
            mail_tm_service=MailTm(logger=logger),
            conta_repository=ArquivoContaRepository(config.executor.users_file),
            db_repository=None,
            config=config.executor,
            proxy_config=config.proxy,
            logger=logger
        )
        
        # Carrega contas
        contas = executor.conta_repository.listar()
        
        # Filtra por emails se especificado
        if request.emails:
            contas = [c for c in contas if c.email in request.emails]
        
        if not contas:
            return ExecutorResponse(
                success=False,
                message="Nenhuma conta encontrada",
                processed=0
            )
        
        # Executa
        executor.executar(acoes=request.actions, contas=contas)
        
        return ExecutorResponse(
            success=True,
            message=f"Execução concluída para {len(contas)} contas",
            processed=len(contas)
        )
        
    except Exception as e:
        logger.erro(f"Erro no executor: {e}")
        return ExecutorResponse(
            success=False,
            message=str(e),
            processed=0
        )


@router.post("/enqueue")
def enqueue_job(req: Request, email: str, actions: Optional[List[str]] = None):
    """Enfileira um job para execução em background."""
    queue = getattr(req.app.state, "task_queue", None)
    
    if queue is None:
        return {"success": False, "message": "Redis não disponível"}
    
    from raxy.adapters.http.tasks import run_farm_task
    
    job = queue.enqueue(run_farm_task, email, actions)
    return {
        "success": True,
        "job_id": job.id,
        "status": "enqueued"
    }


@router.get("/job/{job_id}", response_model=JobStatusResponse)
def get_job_status(req: Request, job_id: str) -> JobStatusResponse:
    """Verifica o status de um job."""
    from rq.job import Job
    
    redis_conn = getattr(req.app.state, "redis_conn", None)
    if redis_conn is None:
        return JobStatusResponse(
            job_id=job_id,
            status="error",
            message="Redis não disponível"
        )
    
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        return JobStatusResponse(
            job_id=job_id,
            status=job.get_status(),
            progress=job.meta.get("progress"),
            result=job.result if job.is_finished else None
        )
    except Exception as e:
        return JobStatusResponse(
            job_id=job_id,
            status="not_found",
            message=str(e)
        )


__all__ = ["router"]