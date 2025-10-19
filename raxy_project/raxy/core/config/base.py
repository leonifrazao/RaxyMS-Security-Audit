"""
Classes base para o sistema de configuração.

Define a estrutura base e funcionalidades comuns para todas as configurações.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields, MISSING
from pathlib import Path
from typing import Any, Dict, Optional, TypeVar, Type, Union, get_type_hints, get_origin, get_args

T = TypeVar('T')


@dataclass
class ConfigField:
    """
    Metadados de um campo de configuração.
    
    Attributes:
        default: Valor padrão
        env_var: Nome da variável de ambiente
        description: Descrição do campo
        required: Se é obrigatório
        validator: Função de validação customizada
    """
    default: Any = MISSING
    env_var: Optional[str] = None
    description: str = ""
    required: bool = False
    validator: Optional[callable] = None


class BaseConfig(ABC):
    """
    Classe base para configurações.
    
    Fornece funcionalidades comuns como carregamento de variáveis
    de ambiente, validação e serialização.
    """
    
    @classmethod
    def from_env(cls: Type[T], prefix: str = "") -> T:
        """
        Carrega configuração de variáveis de ambiente.
        
        Args:
            prefix: Prefixo para variáveis de ambiente
            
        Returns:
            Instância da configuração
        """
        config_data = {}
        
        # Obtém hints de tipo da classe
        type_hints = get_type_hints(cls)
        
        # Processa cada campo
        for field_info in fields(cls):
            field_name = field_info.name
            field_type = type_hints.get(field_name, str)
            
            # Determina nome da variável de ambiente
            env_var = f"{prefix}{field_name.upper()}"
            
            # Obtém metadados do campo se existir
            if hasattr(field_info, 'metadata'):
                metadata = field_info.metadata.get('config', ConfigField(default=None))
                if metadata.env_var:
                    env_var = metadata.env_var
            
            # Tenta obter valor do ambiente
            env_value = os.getenv(env_var)
            
            if env_value is not None:
                config_data[field_name] = cls._parse_value(env_value, field_type)
            elif field_info.default != MISSING:
                config_data[field_name] = field_info.default
            elif field_info.default_factory != MISSING:
                config_data[field_name] = field_info.default_factory()
        
        return cls(**config_data)
    
    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """
        Carrega configuração de um dicionário.
        
        Args:
            data: Dicionário com dados
            
        Returns:
            Instância da configuração
        """
        # Filtra apenas campos válidos
        valid_fields = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        
        return cls(**filtered_data)
    
    @classmethod
    def _parse_value(cls, value: str, target_type: Type) -> Any:
        """
        Converte string para o tipo desejado.
        
        Args:
            value: Valor string
            target_type: Tipo alvo
            
        Returns:
            Valor convertido
        """
        # Trata tipos especiais
        origin = get_origin(target_type)
        
        # Optional
        if origin is Union:
            args = get_args(target_type)
            if len(args) == 2 and type(None) in args:
                # É Optional[T]
                actual_type = args[0] if args[1] is type(None) else args[1]
                if value.lower() in ('none', 'null', ''):
                    return None
                return cls._parse_value(value, actual_type)
        
        # List
        if origin in (list, List):
            item_type = get_args(target_type)[0] if get_args(target_type) else str
            items = value.split(',')
            return [cls._parse_value(item.strip(), item_type) for item in items if item.strip()]
        
        # Dict
        if origin in (dict, Dict):
            import json
            return json.loads(value)
        
        # Path
        if target_type is Path:
            return Path(value)
        
        # Bool
        if target_type is bool:
            return value.lower() in ('true', '1', 'yes', 'on', 't', 'y')
        
        # Int
        if target_type is int:
            return int(value)
        
        # Float
        if target_type is float:
            return float(value)
        
        # String (default)
        return value
    
    def validate(self) -> None:
        """
        Valida a configuração.
        
        Raises:
            ValueError: Se algum campo for inválido
        """
        for field_info in fields(self):
            field_value = getattr(self, field_info.name)
            
            # Verifica campos obrigatórios
            if hasattr(field_info, 'metadata'):
                metadata = field_info.metadata.get('config', ConfigField(default=None))
                
                if metadata.required and field_value is None:
                    raise ValueError(f"Campo obrigatório não definido: {field_info.name}")
                
                # Executa validador customizado
                if metadata.validator and field_value is not None:
                    try:
                        metadata.validator(field_value)
                    except Exception as e:
                        raise ValueError(f"Validação falhou para {field_info.name}: {e}")
        
        # Validação específica da subclasse
        self._validate_specific()
    
    @abstractmethod
    def _validate_specific(self) -> None:
        """
        Validação específica da subclasse.
        
        Deve ser implementado pelas subclasses para
        adicionar validações específicas.
        """
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Converte configuração para dicionário.
        
        Returns:
            Dicionário com a configuração
        """
        result = {}
        for field_info in fields(self):
            value = getattr(self, field_info.name)
            
            # Converte Path para string
            if isinstance(value, Path):
                value = str(value)
            # Converte objetos complexos recursivamente
            elif hasattr(value, 'to_dict'):
                value = value.to_dict()
            elif isinstance(value, list):
                value = [
                    item.to_dict() if hasattr(item, 'to_dict') else item
                    for item in value
                ]
            
            result[field_info.name] = value
        
        return result
    
    def to_env_dict(self, prefix: str = "") -> Dict[str, str]:
        """
        Converte configuração para variáveis de ambiente.
        
        Args:
            prefix: Prefixo para as variáveis
            
        Returns:
            Dicionário com variáveis de ambiente
        """
        env_dict = {}
        
        for field_info in fields(self):
            field_value = getattr(self, field_info.name)
            
            if field_value is None:
                continue
            
            # Determina nome da variável
            env_var = f"{prefix}{field_info.name.upper()}"
            
            if hasattr(field_info, 'metadata'):
                metadata = field_info.metadata.get('config', ConfigField(default=None))
                if metadata.env_var:
                    env_var = metadata.env_var
            
            # Converte valor para string
            if isinstance(field_value, bool):
                env_value = 'true' if field_value else 'false'
            elif isinstance(field_value, (list, tuple)):
                env_value = ','.join(str(item) for item in field_value)
            elif isinstance(field_value, dict):
                import json
                env_value = json.dumps(field_value)
            elif isinstance(field_value, Path):
                env_value = str(field_value)
            else:
                env_value = str(field_value)
            
            env_dict[env_var] = env_value
        
        return env_dict
    
    def __repr__(self) -> str:
        """Representação string da configuração."""
        items = []
        for field_info in fields(self):
            value = getattr(self, field_info.name)
            # Oculta valores sensíveis
            if 'password' in field_info.name.lower() or 'token' in field_info.name.lower():
                value = '***'
            items.append(f"{field_info.name}={value}")
        
        return f"{self.__class__.__name__}({', '.join(items)})"
