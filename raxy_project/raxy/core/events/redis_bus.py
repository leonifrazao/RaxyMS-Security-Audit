"""Implementação do Event Bus usando Redis Pub/Sub."""

from __future__ import annotations

import json
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Optional

try:
    import redis
    from redis.client import PubSub
except ImportError:
    redis = None  # type: ignore
    PubSub = None  # type: ignore

from raxy.interfaces.services import IEventBus, ILoggingService
from raxy.core.exceptions import DependencyException, ResourceException


class RedisEventBus(IEventBus):
    """
    Event Bus implementado com Redis Pub/Sub.
    
    Características:
    - Assíncrono e desacoplado
    - Múltiplos subscribers por evento
    - Serialização JSON automática
    - Thread-safe
    - Reconexão automática
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        prefix: str = "raxy:events:",
        logger: Optional[ILoggingService] = None,
    ):
        """
        Inicializa o Redis Event Bus.
        
        Args:
            host: Host do Redis
            port: Porta do Redis
            db: Database do Redis
            password: Senha (opcional)
            prefix: Prefixo para canais de eventos
            logger: Logger customizado
        """
        if redis is None:
            raise DependencyException(
                "Redis não está instalado. Instale com: pip install redis",
                details={"package": "redis"}
            )
        
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.prefix = prefix
        
        # Logger
        if logger:
            self._logger = logger
        else:
            from raxy.core.logging import get_logger
            self._logger = get_logger()
        
        # Conexões
        self._client: Optional[redis.Redis] = None
        self._pubsub: Optional[PubSub] = None
        
        # Handlers registrados
        self._handlers: Dict[str, List[Callable]] = {}
        
        # Thread de escuta
        self._listener_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        
        # Controle do servidor Redis
        self._redis_process: Optional[subprocess.Popen] = None
        self._auto_started_redis = False
    
    def _get_channel_name(self, event_name: str) -> str:
        """Retorna nome completo do canal."""
        return f"{self.prefix}{event_name}"
    
    def _is_redis_running(self) -> bool:
        """Verifica se o Redis está rodando."""
        try:
            test_client = redis.Redis(
                host=self.host,
                port=self.port,
                decode_responses=True,
                socket_connect_timeout=2
            )
            test_client.ping()
            return True
        except (redis.ConnectionError, redis.TimeoutError):
            return False
    
    def _start_redis_server(self) -> bool:
        """
        Tenta iniciar o servidor Redis localmente.
        
        Returns:
            True se conseguiu iniciar, False caso contrário
        """
        if self.host not in ("localhost", "127.0.0.1"):
            self._logger.aviso(f"Não é possível iniciar Redis em host remoto: {self.host}")
            return False
        
        try:
            self._logger.info("Tentando iniciar servidor Redis...")
            
            # Tenta iniciar Redis
            self._redis_process = subprocess.Popen(
                ["redis-server", "--port", str(self.port), "--daemonize", "no"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            
            # Aguarda alguns segundos para o Redis iniciar
            time.sleep(2)
            
            # Verifica se iniciou
            if self._is_redis_running():
                self._logger.sucesso(f"✅ Redis iniciado automaticamente na porta {self.port}")
                self._auto_started_redis = True
                return True
            else:
                self._logger.erro("Falha ao iniciar Redis")
                if self._redis_process:
                    self._redis_process.terminate()
                    self._redis_process = None
                return False
                
        except FileNotFoundError:
            self._logger.erro(
                "redis-server não encontrado. Instale com: sudo apt install redis-server ou nix-shell"
            )
            return False
        except Exception as e:
            self._logger.erro(f"Erro ao tentar iniciar Redis: {e}")
            return False
    
    def _connect(self) -> None:
        """Conecta ao Redis, iniciando o servidor se necessário."""
        # Primeiro tenta conectar
        if not self._is_redis_running():
            self._logger.aviso(f"Redis não está rodando em {self.host}:{self.port}")
            
            # Tenta iniciar automaticamente
            if not self._start_redis_server():
                raise ResourceException(
                    f"Redis não está disponível em {self.host}:{self.port} e não foi possível iniciá-lo",
                    details={"host": self.host, "port": self.port}
                )
        
        try:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
            )
            # Testa conexão
            self._client.ping()
            self._logger.info(f"Conectado ao Redis: {self.host}:{self.port}")
        except redis.ConnectionError as e:
            raise ResourceException(
                f"Falha ao conectar ao Redis: {self.host}:{self.port}",
                details={"host": self.host, "port": self.port},
                cause=e
            )
    
    def publish(self, event_name: str, data: Dict[str, Any]) -> None:
        """Publica um evento no Redis."""
        if not self._client:
            raise ResourceException("Event Bus não está conectado. Chame start() primeiro.")
        
        channel = self._get_channel_name(event_name)
        
        try:
            # Serializa dados
            payload = json.dumps(data)
            
            # Publica no Redis
            subscribers = self._client.publish(channel, payload)
            
            self._logger.debug(
                f"Evento publicado: {event_name} ({subscribers} subscribers)"
            )
        except (json.JSONEncodeError, redis.RedisError) as e:
            self._logger.erro(f"Erro ao publicar evento {event_name}: {e}")
            raise ResourceException(
                f"Erro ao publicar evento: {event_name}",
                details={"event": event_name, "error": str(e)},
                cause=e
            )
    
    def subscribe(
        self,
        event_name: str,
        handler: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Inscreve um handler para um evento."""
        with self._lock:
            if event_name not in self._handlers:
                self._handlers[event_name] = []
            
            if handler not in self._handlers[event_name]:
                self._handlers[event_name].append(handler)
                self._logger.info(f"Handler registrado para evento: {event_name}")
                
                # Se já está rodando, inscreve no pubsub
                if self._running and self._pubsub:
                    channel = self._get_channel_name(event_name)
                    self._pubsub.subscribe(channel)
    
    def unsubscribe(
        self,
        event_name: str,
        handler: Optional[Callable] = None
    ) -> None:
        """Remove inscrição de um evento."""
        with self._lock:
            if event_name not in self._handlers:
                return
            
            if handler is None:
                # Remove todos os handlers
                del self._handlers[event_name]
                self._logger.info(f"Todos os handlers removidos do evento: {event_name}")
            elif handler in self._handlers[event_name]:
                # Remove handler específico
                self._handlers[event_name].remove(handler)
                self._logger.info(f"Handler removido do evento: {event_name}")
                
                # Se não há mais handlers, remove do pubsub
                if not self._handlers[event_name]:
                    del self._handlers[event_name]
            
            # Desincreve do pubsub se não há mais handlers
            if event_name not in self._handlers and self._pubsub:
                channel = self._get_channel_name(event_name)
                self._pubsub.unsubscribe(channel)
    
    def _listen_loop(self) -> None:
        """Loop de escuta de eventos (roda em thread separada)."""
        self._logger.info("Iniciando listener de eventos...")
        
        while self._running and self._pubsub:
            try:
                message = self._pubsub.get_message(timeout=1.0)
                
                if message and message["type"] == "message":
                    channel = message["channel"]
                    payload = message["data"]
                    
                    # Remove prefixo do canal
                    event_name = channel.replace(self.prefix, "", 1)
                    
                    # Deserializa dados
                    try:
                        data = json.loads(payload)
                    except json.JSONDecodeError:
                        self._logger.erro(f"Payload inválido no evento {event_name}: {payload}")
                        continue
                    
                    # Executa handlers
                    with self._lock:
                        handlers = self._handlers.get(event_name, [])
                    
                    for handler in handlers:
                        try:
                            handler(data)
                        except Exception as e:
                            self._logger.erro(f"Erro no handler do evento {event_name}: {e}")
            except redis.ConnectionError:
                self._logger.aviso("Conexão perdida. Tentando reconectar...")
                self._connect()
            except Exception as e:
                self._logger.erro(f"Erro no listener de eventos: {e}")
        
        self._logger.info("Listener de eventos parado.")
    
    def start(self) -> None:
        """Inicia o event bus."""
        if self._running:
            self._logger.aviso("Event Bus já está rodando.")
            return
        
        # Conecta ao Redis
        self._connect()
        
        # Cria PubSub
        if not self._client:
            raise ResourceException("Client Redis não disponível")
        
        self._pubsub = self._client.pubsub(ignore_subscribe_messages=True)
        
        # Inscreve em canais já registrados
        for event_name in self._handlers.keys():
            channel = self._get_channel_name(event_name)
            self._pubsub.subscribe(channel)
        
        # Inicia thread de escuta
        self._running = True
        self._listener_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="RedisEventBusListener"
        )
        self._listener_thread.start()
        
        # Aguarda thread estar rodando
        time.sleep(0.1)
        
        self._logger.sucesso("Event Bus iniciado com sucesso.")
    
    def stop(self) -> None:
        """Para o event bus."""
        if not self._running:
            return
        
        self._logger.info("Parando Event Bus...")
        
        # Para thread de escuta
        self._running = False
        if self._listener_thread:
            self._listener_thread.join(timeout=5.0)
        
        # Fecha PubSub
        if self._pubsub:
            self._pubsub.close()
            self._pubsub = None
        
        # Fecha client
        if self._client:
            self._client.close()
            self._client = None
        
        # Para servidor Redis se foi iniciado automaticamente
        if self._auto_started_redis and self._redis_process:
            self._logger.info("Parando servidor Redis auto-iniciado...")
            try:
                self._redis_process.terminate()
                self._redis_process.wait(timeout=5)
                self._logger.info("Redis parado.")
            except Exception as e:
                self._logger.aviso(f"Erro ao parar Redis: {e}")
            finally:
                self._redis_process = None
                self._auto_started_redis = False
        
        self._logger.info("Event Bus parado.")
    
    def is_running(self) -> bool:
        """Verifica se o bus está rodando."""
        return self._running
    
    def __enter__(self):
        """Context manager enter."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
