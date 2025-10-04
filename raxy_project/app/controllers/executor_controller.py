"""Endpoints para orquestrar execuções em lote."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends

from dependencies import (
    get_account_repository,
    get_database_repository,
    get_executor_service,
    get_logging_service,
)
from schemas import (
    AccountPayload,
    AccountSource,
    ExecutorBatchRequest,
    ExecutorBatchResponse,
)
from raxy.domain import Conta
from raxy.interfaces.repositories import IContaRepository, IDatabaseRepository
from raxy.interfaces.services import IExecutorEmLoteService, ILoggingService

router = APIRouter(prefix="/executor", tags=["Executor"])


def _executar_batch(
    executor: IExecutorEmLoteService,
    logger: ILoggingService,
    acoes: list[str] | None,
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


@router.post("/run", response_model=ExecutorBatchResponse)
def run_executor(
    payload: ExecutorBatchRequest,
    background_tasks: BackgroundTasks,
    executor_service: IExecutorEmLoteService = Depends(get_executor_service),
    logger: ILoggingService = Depends(get_logging_service),
    conta_repository: IContaRepository = Depends(get_account_repository),
    database_repository: IDatabaseRepository = Depends(get_database_repository),
) -> ExecutorBatchResponse:
    """Registra uma execução em lote para ser processada em segundo plano."""

    contas_manual = _build_manual_accounts(payload.manual_accounts())
    source = _determine_source(payload, contas_manual)

    if source is AccountSource.DATABASE:
        contas_para_executar = _build_database_accounts(database_repository, logger)
    elif contas_manual:
        contas_para_executar = contas_manual
    else:
        contas_para_executar = conta_repository.listar()

    background_tasks.add_task(
        _executar_batch,
        executor_service,
        logger,
        payload.actions,
        contas_para_executar,
        source,
    )

    return ExecutorBatchResponse(
        status="scheduled",
        detail="Execução em lote iniciada em background",
        source=source,
    )


def _determine_source(
    payload: ExecutorBatchRequest, contas_manual: list[Conta]
) -> AccountSource:
    if contas_manual:
        return AccountSource.MANUAL
    if payload.source is AccountSource.DATABASE:
        return AccountSource.DATABASE
    return AccountSource.FILE


def _build_manual_accounts(contas_payload: list[AccountPayload]) -> list[Conta]:
    contas: list[Conta] = []
    for item in contas_payload:
        perfil = item.profile_id or item.email
        proxy = item.proxy or ""
        contas.append(Conta(email=item.email, senha=item.password, id_perfil=perfil, proxy=proxy))
    return contas


def _build_database_accounts(
    database_repository: IDatabaseRepository,
    logger: ILoggingService,
) -> list[Conta]:
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
        proxy = registro.get("proxy") or registro.get("proxy_uri") or ""
        contas.append(Conta(email=email, senha=senha, id_perfil=perfil, proxy=proxy))
    return contas
