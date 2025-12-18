"""
Worker Entrypoint.

Script to start the RQ worker process using the application container.
"""

import sys
import os

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from redis import Redis
from rq import Worker, Queue
from dotenv import load_dotenv

from raxy.infrastructure.config.config import get_config

# Load env vars
load_dotenv()

def start_worker():
    """Starts the RQ worker."""
    container = get_container()
    config = container.config()
    
    if not config.events.enabled:
        print("❌ Redis is disabled in config. Cannot start worker.")
        sys.exit(1)
        
    print(f"🔌 Connecting to Redis at {config.events.host}:{config.events.port}...")
    
    redis_conn = Redis(
        host=config.events.host,
        port=config.events.port,
        db=config.events.db,
        password=config.events.password,
    )
    
    # Create queue with explicit connection
    queue = Queue(connection=redis_conn)
    
    worker_name = f"raxy-worker-{sys.argv[1] if len(sys.argv) > 1 else '1'}"
    print(f"👷 Starting worker {worker_name}...")
    
    # Start worker with explicit connection
    w = Worker([queue], connection=redis_conn, name=worker_name)
    w.work()

if __name__ == "__main__":
    start_worker()
