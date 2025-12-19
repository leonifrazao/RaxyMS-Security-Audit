"""
Carregador de configuração (Loader).

Responsável por ler arquivos de configuração (YAML) e aplicar overrides
via variáveis de ambiente, retornando uma instância válida de AppConfig.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from raxy.config.models import AppConfig


class ConfigLoaderException(Exception):
    """Erro ao carregar configurações."""
    pass


class ConfigLoader:
    """Carregador de configurações."""
    
    DEFAULT_FILENAME = "config.yaml"

    @classmethod
    def load(cls, path: Optional[Path | str] = None) -> AppConfig:
        """
        Carrega a configuração completa.
        
        Ordem de precedência:
        1. Defaults do código
        2. Arquivo YAML
        3. Variáveis de Ambiente (RAXY_*)
        
        Args:
            path: Caminho opcional para o arquivo config.yaml
            
        Returns:
            AppConfig: Configuração validada e carregada.
            
        Raises:
            ConfigLoaderException: Se houver erro de parsing ou IO.
        """
        config_path = Path(path) if path else Path(cls.DEFAULT_FILENAME)
        
        # 1. Carregar do Arquivo
        file_data = cls._read_yaml(config_path)
        
        # 2. Aplicar Variáveis de Ambiente
        merged_data = cls._apply_env_overrides(file_data)
        
        # 3. Construir e Validar Modelo
        try:
            return AppConfig.from_dict(merged_data)
        except Exception as e:
            raise ConfigLoaderException(f"Erro ao validar configuração: {e}") from e

    @staticmethod
    def _read_yaml(path: Path) -> Dict[str, Any]:
        """Lê arquivo YAML com segurança."""
        if not path.exists():
            return {}
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            raise ConfigLoaderException(f"Erro ao ler arquivo {path}: {e}") from e

    @classmethod
    def _apply_env_overrides(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Aplica overrides via variáveis de ambiente (RAXY_...)."""
        # Cópia para não mutar o original
        out = data.copy()
        
        # Mapeamento: ENV_VAR -> (path.no.dict, type_func)
        overrides = {
            "RAXY_DEBUG": (["debug"], cls._parse_bool),
            "RAXY_ENVIRONMENT": (["environment"], str),
            "RAXY_MAX_WORKERS": (["executor", "max_workers"], int),
            "RAXY_USERS_FILE": (["executor", "users_file"], str),
            "RAXY_HEADLESS": (["session", "headless"], cls._parse_bool),
        }
        
        for env_var, (keys, type_func) in overrides.items():
            val = os.getenv(env_var)
            if val is not None:
                cls._set_nested(out, keys, type_func(val))
                
        return out

    @staticmethod
    def _set_nested(data: Dict[str, Any], keys: list, value: Any) -> None:
        """Helper para setar valor em dict aninhado."""
        current = data
        for i, key in enumerate(keys[:-1]):
            current = current.setdefault(key, {})
        current[keys[-1]] = value

    @staticmethod
    def _parse_bool(val: str) -> bool:
        """Parse seguro de boolean."""
        return val.lower() in ("true", "1", "yes", "on")
