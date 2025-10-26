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
    
    # ========================================================================
    # STATE MANAGEMENT - Reutilização da infraestrutura Redis existente
    # ========================================================================
    
    def set_state(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """
        Armazena estado no Redis (reutiliza conexão existente).
        
        Permite compartilhamento de estado entre múltiplos processos/workers
        sem adicionar nova infraestrutura. Usa a MESMA conexão Redis já paga.
        
        Args:
            key: Chave para identificar o estado
            value: Valor a ser armazenado (será serializado em JSON)
            ttl: Tempo de vida em segundos (opcional)
            
        Returns:
            bool: True se salvou com sucesso, False caso contrário
            
        Example:
            >>> bus.set_state("session:user@email.com:cookies", {"token": "abc"}, ttl=3600)
            True
        """
        if not self._client:
            self._logger.aviso("Redis client não disponível para state management")
            return False
        
        try:
            full_key = f"{self.prefix}state:{key}"
            serialized = json.dumps(value)
            
            if ttl:
                result = self._client.setex(full_key, ttl, serialized)
            else:
                result = self._client.set(full_key, serialized)
            
            self._logger.debug(f"Estado salvo: {key} (TTL: {ttl}s)")
            return bool(result)
            
        except (json.JSONEncodeError, redis.RedisError) as e:
            self._logger.erro(f"Erro ao salvar estado {key}: {e}")
            return False
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """
        Recupera estado do Redis.
        
        Args:
            key: Chave do estado
            default: Valor padrão se não encontrado
            
        Returns:
            Any: Valor deserializado ou default
            
        Example:
            >>> cookies = bus.get_state("session:user@email.com:cookies", {})
            >>> print(cookies)
            {"token": "abc"}
        """
        if not self._client:
            self._logger.debug(f"Redis client não disponível, retornando default para {key}")
            return default
        
        try:
            full_key = f"{self.prefix}state:{key}"
            value = self._client.get(full_key)
            
            if value is None:
                self._logger.debug(f"Estado não encontrado: {key}")
                return default
            
            deserialized = json.loads(value)
            self._logger.debug(f"Estado recuperado: {key}")
            return deserialized
            
        except (json.JSONDecodeError, redis.RedisError) as e:
            self._logger.erro(f"Erro ao ler estado {key}: {e}")
            return default
    
    def delete_state(self, key: str) -> bool:
        """
        Remove estado do Redis.
        
        Args:
            key: Chave do estado
            
        Returns:
            bool: True se removeu, False caso contrário
            
        Example:
            >>> bus.delete_state("session:user@email.com:cookies")
            True
        """
        if not self._client:
            return False
        
        try:
            full_key = f"{self.prefix}state:{key}"
            deleted = self._client.delete(full_key)
            
            if deleted > 0:
                self._logger.debug(f"Estado removido: {key}")
                return True
            else:
                self._logger.debug(f"Estado não existia: {key}")
                return False
                
        except redis.RedisError as e:
            self._logger.erro(f"Erro ao deletar estado {key}: {e}")
            return False
    
    def exists_state(self, key: str) -> bool:
        """
        Verifica se um estado existe no Redis.
        
        Args:
            key: Chave do estado
            
        Returns:
            bool: True se existe, False caso contrário
        """
        if not self._client:
            return False
        
        try:
            full_key = f"{self.prefix}state:{key}"
            return bool(self._client.exists(full_key))
        except redis.RedisError as e:
            self._logger.erro(f"Erro ao verificar existência do estado {key}: {e}")
            return False
    
    def get_state_ttl(self, key: str) -> Optional[int]:
        """
        Retorna o TTL restante de um estado em segundos.
        
        Args:
            key: Chave do estado
            
        Returns:
            Optional[int]: Segundos restantes ou None se não existe/sem TTL
        """
        if not self._client:
            return None
        
        try:
            full_key = f"{self.prefix}state:{key}"
            ttl = self._client.ttl(full_key)
            
            # -2 significa que a chave não existe
            # -1 significa que não tem TTL definido
            if ttl == -2:
                return None
            elif ttl == -1:
                return None
            else:
                return ttl
                
        except redis.RedisError as e:
            self._logger.erro(f"Erro ao obter TTL do estado {key}: {e}")
            return None
    
    def set_state_hash(
        self, 
        hash_key: str, 
        field: str, 
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Armazena um campo em um hash Redis (para estados estruturados).
        
        Útil para armazenar múltiplos campos relacionados de forma eficiente.
        
        Args:
            hash_key: Nome do hash
            field: Campo dentro do hash
            value: Valor a ser armazenado
            ttl: TTL para o hash inteiro (opcional)
            
        Returns:
            bool: True se salvou com sucesso
            
        Example:
            >>> bus.set_state_hash("session:user@email.com", "cookies", {...})
            >>> bus.set_state_hash("session:user@email.com", "user_agent", "...")
        """
        if not self._client:
            return False
        
        try:
            full_key = f"{self.prefix}state:{hash_key}"
            serialized = json.dumps(value)
            
            result = self._client.hset(full_key, field, serialized)
            
            if ttl:
                self._client.expire(full_key, ttl)
            
            self._logger.debug(f"Estado hash salvo: {hash_key}.{field}")
            return True
            
        except (json.JSONEncodeError, redis.RedisError) as e:
            self._logger.erro(f"Erro ao salvar estado hash {hash_key}.{field}: {e}")
            return False
    
    def get_state_hash(
        self, 
        hash_key: str, 
        field: str, 
        default: Any = None
    ) -> Any:
        """
        Recupera um campo de um hash Redis.
        
        Args:
            hash_key: Nome do hash
            field: Campo a recuperar
            default: Valor padrão se não encontrado
            
        Returns:
            Any: Valor deserializado ou default
        """
        if not self._client:
            return default
        
        try:
            full_key = f"{self.prefix}state:{hash_key}"
            value = self._client.hget(full_key, field)
            
            if value is None:
                return default
            
            return json.loads(value)
            
        except (json.JSONDecodeError, redis.RedisError) as e:
            self._logger.erro(f"Erro ao ler estado hash {hash_key}.{field}: {e}")
            return default
    
    def get_state_hash_all(self, hash_key: str) -> Dict[str, Any]:
        """
        Recupera todos os campos de um hash Redis.
        
        Args:
            hash_key: Nome do hash
            
        Returns:
            Dict[str, Any]: Dicionário com todos os campos deserializados
        """
        if not self._client:
            return {}
        
        try:
            full_key = f"{self.prefix}state:{hash_key}"
            hash_data = self._client.hgetall(full_key)
            
            result = {}
            for field, value in hash_data.items():
                try:
                    result[field] = json.loads(value)
                except json.JSONDecodeError:
                    result[field] = value
            
            return result
            
        except redis.RedisError as e:
            self._logger.erro(f"Erro ao ler estado hash completo {hash_key}: {e}")
            return {}
    
    # ========================================================================
    # Context Manager
    # ========================================================================
    
    def __enter__(self):
        """Context manager enter."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
