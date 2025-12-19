"""
Funções de validação reutilizáveis.

Este módulo contém funções puras para validar dados de configuração e inputs,
garantindo integridade dos dados antes da utilização.
"""

from typing import Any, List, Set, Optional, TypeVar, Iterable
from pathlib import Path

# Tipo genérico para listas
T = TypeVar("T")


class ValidationException(Exception):
    """Erro base para falhas de validação."""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.details = details or {}


def validate_positive_int(value: int, field_name: str, min_value: int = 1) -> None:
    """
    Valida se um número inteiro é positivo ou maior que um mínimo.
    
    Args:
        value: O valor a ser validado.
        field_name: Nome do campo para mensagem de erro.
        min_value: Valor mínimo aceitável (default: 1).
        
    Raises:
        ValidationException: Se o valor for menor que min_value.
    """
    if not isinstance(value, int):
         raise ValidationException(
            f"{field_name} deve ser um número inteiro.",
            details={"value": value, "type": type(value).__name__}
        )
    
    if value < min_value:
        raise ValidationException(
            f"{field_name} deve ser >= {min_value}", 
            details={"value": value, "min_value": min_value}
        )


def validate_positive_float(value: float, field_name: str, min_value: float = 1.0) -> None:
    """
    Valida se um número float é maior que um mínimo.
    
    Args:
        value: O valor a ser validado.
        field_name: Nome do campo.
        min_value: Valor mínimo aceitável.
    """
    if not isinstance(value, (float, int)):
         raise ValidationException(
            f"{field_name} deve ser um número.",
            details={"value": value, "type": type(value).__name__}
        )

    if value < min_value:
        raise ValidationException(
            f"{field_name} deve ser >= {min_value}", 
            details={"value": value, "min_value": min_value}
        )


def validate_not_empty(value: Iterable[Any], field_name: str) -> None:
    """
    Valida se uma coleção (lista, set, string) não está vazia.
    
    Args:
        value: A coleção a validar.
        field_name: Nome do campo.
    """
    if not value:
        raise ValidationException(f"{field_name} não pode estar vazio")


def validate_subset(items: Iterable[str], valid_set: Set[str], field_name: str) -> None:
    """
    Valida se todos os itens de uma lista pertencem a um conjunto permitido.
    
    Args:
        items: Itens a validar.
        valid_set: Conjunto de valores permitidos.
        field_name: Nome do campo.
    """
    invalid = set(items) - valid_set
    if invalid:
        raise ValidationException(
            f"{field_name} contém itens inválidos: {invalid}", 
            details={"invalid_items": list(invalid), "valid_options": list(valid_set)}
        )


def validate_choice(value: str, valid_choices: Set[str], field_name: str) -> None:
    """
    Valida se um valor único está dentro das opções permitidas.
    
    Args:
        value: Valor a validar.
        valid_choices: Conjunto de escolhas permitidas.
        field_name: Nome do campo.
    """
    if value not in valid_choices:
        raise ValidationException(
            f"{field_name} inválido: {value}. Use um dos: {', '.join(valid_choices)}",
            details={"value": value, "valid_choices": list(valid_choices)}
        )


def ensure_path_exists(path: Optional[str | Path]) -> Optional[Path]:
    """
    Garante que o diretório pai de um caminho exista.
    Se o caminho for um diretório, cria ele mesmo.
    
    Args:
        path: Caminho a verificar.
        
    Returns:
        Path: Objeto Path resolvido ou None se path for None.
    """
    if path is not None:
        resolved = Path(path).expanduser().resolve()
        # Se não tem extensão, assume que é diretório e cria
        if not resolved.suffix:
            resolved.mkdir(parents=True, exist_ok=True)
        else:
            # Se tem extensão, garante que o pai existe
            resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved
    return None


def validate_type(value: Any, expected_type: type, field_name: str) -> None:
    """
    Valida estritamente se o valor corresponde ao tipo esperado.
    Não aceita conversão implícita (ex: "true" para bool).
    
    Args:
        value: Valor a validar.
        expected_type: Tipo esperado (int, bool, str, float, list, dict).
        field_name: Nome do campo.
        
    Raises:
        ValidationException: Se o tipo estiver incorreto.
    """
    if value is None:
        return  # Optionals são tratados pelo type hint do dataclass ou default=None
        
    if not isinstance(value, expected_type):
        # Caso especial: bool é subclasse de int, mas queremos diferenciar
        if expected_type is int and isinstance(value, bool):
             raise ValidationException(
                f"{field_name} deve ser um inteiro, não booleano.",
                details={"value": value, "expected": "int", "got": "bool"}
            )
            
        raise ValidationException(
            f"{field_name} deve ser do tipo {expected_type.__name__}.",
            details={
                "value": value, 
                "expected": expected_type.__name__, 
                "got": type(value).__name__
            }
        )
