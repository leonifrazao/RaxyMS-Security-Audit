"""
Configuração centralizada do sistema de logging.

Define todas as configurações e parâmetros do sistema de logging,
permitindo customização via variáveis de ambiente ou programaticamente.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class LoggerConfig:
    """
    Configuração centralizada do sistema de logging.
    
    Attributes:
        nome: Nome do logger
        nivel_minimo: Nível mínimo de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        arquivo_log: Caminho para arquivo de log
        sobrescrever_arquivo: Se deve sobrescrever arquivo existente
        mostrar_tempo: Se deve mostrar timestamp
        mostrar_localizacao: Se deve mostrar arquivo/linha/função
        usar_cores: Se deve usar cores no console
        rotacao_arquivo: Configuração de rotação (ex: "100 MB", "1 day")
        retencao_arquivo: Tempo de retenção dos logs (ex: "7 days")
        compressao_arquivo: Tipo de compressão (ex: "zip", "gz")
        diretorio_erros: Diretório para logs de erro
        formato_detalhado: Se deve usar formato detalhado
        max_workers: Número máximo de workers para processamento async
        buffer_size: Tamanho do buffer de logs
    """
    
    # Identificação
    nome: str = "raxy"
    
    # Níveis e filtros
    nivel_minimo: str = "INFO"
    
    # Arquivos
    arquivo_log: Optional[Path] = None
    sobrescrever_arquivo: bool = False
    rotacao_arquivo: Optional[str] = "100 MB"
    retencao_arquivo: Optional[str] = "7 days"
    compressao_arquivo: Optional[str] = "zip"
    
    # Formatação
    mostrar_tempo: bool = True
    mostrar_localizacao: bool = True
    usar_cores: bool = True
    formato_detalhado: bool = False
    
    # Diretórios especiais
    diretorio_erros: Optional[Path] = Path("logs/errors")
    
    # Performance
    max_workers: int = 2
    buffer_size: int = 1000
    
    # Limites
    max_message_length: int = 10000
    max_context_depth: int = 10
    
    @classmethod
    def from_env(cls) -> LoggerConfig:
        """
        Cria configuração baseada em variáveis de ambiente.
        
        Variáveis suportadas:
            LOG_LEVEL: Nível mínimo de log
            LOG_FILE: Arquivo de log
            LOG_OVERWRITE: Se deve sobrescrever arquivo
            LOG_COLORS: Se deve usar cores
            LOG_ROTATION: Configuração de rotação
            LOG_RETENTION: Tempo de retenção
            LOG_COMPRESSION: Tipo de compressão
            LOG_ERROR_DIR: Diretório de erros
            
        Returns:
            LoggerConfig: Configuração construída
        """
        config = cls()
        
        # Nível
        if nivel := os.getenv("LOG_LEVEL"):
            config.nivel_minimo = nivel.upper()
        
        # Arquivo
        if arquivo := os.getenv("LOG_FILE"):
            config.arquivo_log = Path(arquivo)
        
        # Flags booleanas
        config.sobrescrever_arquivo = _parse_bool(
            os.getenv("LOG_OVERWRITE"), 
            config.sobrescrever_arquivo
        )
        config.usar_cores = _parse_bool(
            os.getenv("LOG_COLORS"), 
            config.usar_cores
        )
        
        # Rotação e retenção
        if rotacao := os.getenv("LOG_ROTATION"):
            config.rotacao_arquivo = rotacao
        if retencao := os.getenv("LOG_RETENTION"):
            config.retencao_arquivo = retencao
        if compressao := os.getenv("LOG_COMPRESSION"):
            config.compressao_arquivo = compressao
        
        # Diretório de erros
        if erro_dir := os.getenv("LOG_ERROR_DIR"):
            config.diretorio_erros = Path(erro_dir)
        
        return config
    
    def validate(self) -> None:
        """
        Valida a configuração.
        
        Raises:
            ValueError: Se alguma configuração for inválida
        """
        # Valida nível
        niveis_validos = {"DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}
        if self.nivel_minimo.upper() not in niveis_validos:
            raise ValueError(f"Nível inválido: {self.nivel_minimo}")
        
        # Valida limites
        if self.max_workers < 1:
            raise ValueError("max_workers deve ser >= 1")
        if self.buffer_size < 10:
            raise ValueError("buffer_size deve ser >= 10")
        if self.max_message_length < 100:
            raise ValueError("max_message_length deve ser >= 100")
        
        # Cria diretórios se necessário
        if self.arquivo_log:
            self.arquivo_log.parent.mkdir(parents=True, exist_ok=True)
        if self.diretorio_erros:
            self.diretorio_erros.mkdir(parents=True, exist_ok=True)


def _parse_bool(value: Optional[str], default: bool) -> bool:
    """Parse de string para boolean."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


# Mapeamento de níveis
LEVEL_VALUES = {
    "DEBUG": 10,
    "INFO": 20,
    "SUCCESS": 25,  # Nível customizado para sucesso
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

LEVEL_NAMES = {v: k for k, v in LEVEL_VALUES.items()}
