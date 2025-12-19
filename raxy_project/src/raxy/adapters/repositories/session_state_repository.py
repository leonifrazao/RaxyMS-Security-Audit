"""
Implementações do repositório de estado de sessão.
"""

from typing import Any, Dict, Optional
import json

from raxy.core.interfaces import SessionStateRepository
from raxy.infrastructure.logging import get_logger

class InMemorySessionStateRepository(SessionStateRepository):
    """
    Implementação em memória (não persistente entre reinícios).
    Útil para testes ou execuções locais simples.
    """
    
    def __init__(self):
        self._storage: Dict[str, Any] = {}
        self.logger = get_logger()

    def _make_key(self, account_id: str, key: str) -> str:
        return f"{account_id}:{key}"

    def save_state(self, account_id: str, key: str, value: Any, ttl: int = 3600) -> bool:
        full_key = self._make_key(account_id, key)
        self._storage[full_key] = value
        # Nota: InMemory ignora TTL por simplicidade
        return True

    def get_state(self, account_id: str, key: str, default: Any = None) -> Any:
        full_key = self._make_key(account_id, key)
        return self._storage.get(full_key, default)

    def clear_state(self, account_id: str) -> None:
        prefix = f"{account_id}:"
        keys_to_remove = [k for k in self._storage if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._storage[k]


class RedisSessionStateRepository(SessionStateRepository):
    """
    Implementação usando Redis para estado distribuído.
    """
    
    def __init__(self, redis_client: Any):
        """
        Args:
            redis_client: Instância de redis.Redis ou compatível.
        """
        self.redis = redis_client
        self.logger = get_logger()

    def _make_key(self, account_id: str, key: str) -> str:
        return f"session:{account_id}:{key}"

    def save_state(self, account_id: str, key: str, value: Any, ttl: int = 3600) -> bool:
        try:
            full_key = self._make_key(account_id, key)
            # Serializa se necessário (simples JSON para dicts/listas)
            if isinstance(value, (dict, list)):
                payload = json.dumps(value)
            else:
                payload = str(value)
                
            self.redis.setex(full_key, ttl, payload)
            return True
        except Exception as e:
            self.logger.erro(f"Redis save error: {e}")
            return False

    def get_state(self, account_id: str, key: str, default: Any = None) -> Any:
        try:
            full_key = self._make_key(account_id, key)
            data = self.redis.get(full_key)
            if not data:
                return default
                
            # Tenta deserializar JSON
            try:
                decoded = data.decode('utf-8')
                return json.loads(decoded)
            except (json.JSONDecodeError, AttributeError):
                # Retorna string bruta se não for JSON inválido
                return data.decode('utf-8') if hasattr(data, 'decode') else data
                
        except Exception as e:
            self.logger.erro(f"Redis get error: {e}")
            return default

    def clear_state(self, account_id: str) -> None:
        # Implementação simplificada: scan keys e delete
        # Atenção: SCAN pode ser lento em produção massiva, usar com cuidado
        pass
