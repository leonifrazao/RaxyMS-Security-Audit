"""
Background Tasks.

Defines the tasks that can be executed by the RQ worker.
"""

from rq import get_current_job
from raxy.infrastructure.config.config import get_config

def run_farm_task(email: str, actions: list[str] | None = None):
    """
    Background task to run farming logic for a single account.
    """
    job = get_current_job()
    if job:
        job.meta['progress'] = 'starting'
        job.save_meta()
    
    container = get_container()
    
    # Get services from container
    executor = container.executor_service()
    repo = container.conta_repository()
    
    # Find the account
    all_accounts = repo.listar()
    target_account = next((acc for acc in all_accounts if acc.email == email), None)
    
    if not target_account:
        raise ValueError(f"Account {email} not found in repository")
    
    # Run execution
    if job:
        job.meta['progress'] = 'running'
        job.save_meta()
        
    try:
        # Execute for the single account
        result = executor.executar(
            acoes=actions,
            contas=[target_account]
        )
        
        if job:
            job.meta['progress'] = 'completed'
            job.save_meta()
            
        return result
        
    except Exception as e:
        if job:
            job.meta['progress'] = 'failed'
            job.meta['error'] = str(e)
            job.save_meta()
        raise e
