
"""
Implementação do repositório usando SQLite.
"""

from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, List

from raxy.interfaces.database import IDatabaseRepository, IContaRepository
from raxy.models import Conta
from raxy.core.exceptions import DatabaseException, wrap_exception
from raxy.core.logging import get_logger

class SQLiteRepository(IDatabaseRepository, IContaRepository):
    """
    Repositório de dados usando SQLite local.
    """

    def __init__(self, db_path: str | Path = "raxy.db", logger = None):
        """
        Inicializa o repositório SQLite.
        
        Args:
            db_path: Caminho para o arquivo do banco de dados.
            logger: Serviço de log.
        """
        self.db_path = str(db_path)
        self.logger = logger or get_logger()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Cria uma conexão com o banco de dados."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Permite acesso por nome de coluna
            return conn
        except sqlite3.Error as e:
            raise DatabaseException(f"Erro ao conectar ao banco SQLite: {e}", details={"path": self.db_path})

    def _init_db(self):
        """Inicializa o esquema do banco de dados se não existir."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS contas (
            email TEXT PRIMARY KEY,
            senha TEXT NOT NULL,
            id_perfil TEXT,
            proxy TEXT,
            email_backup TEXT,
            senha_email_backup TEXT,
            pontos INTEGER DEFAULT 0,
            ultima_farm TIMESTAMP,
            meta_diaria INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            dados_extras JSON
        );
        """
        try:
            with self._get_connection() as conn:
                conn.execute(create_table_sql)
                
                # Migration simples: verificar e adicionar colunas se faltarem
                cursor = conn.execute("PRAGMA table_info(contas)")
                colunas = [row["name"] for row in cursor.fetchall()]
                
                if "email_backup" not in colunas:
                    self.logger.info("Migrando BD: Adicionando coluna email_backup")
                    conn.execute("ALTER TABLE contas ADD COLUMN email_backup TEXT")
                    
                if "senha_email_backup" not in colunas:
                    self.logger.info("Migrando BD: Adicionando coluna senha_email_backup")
                    conn.execute("ALTER TABLE contas ADD COLUMN senha_email_backup TEXT")
                
                conn.commit()
        except Exception as e:
            raise wrap_exception(e, DatabaseException, "Erro ao inicializar schema do SQLite")

# IContaRepository implementation

    def listar(self) -> List[Conta]:
        """Lista todas as contas retornando objetos Conta."""
        rows = self.listar_contas()
        return [Conta.from_dict(row) for row in rows]

    def salvar(self, conta: Conta) -> Conta:
        """Salva ou atualiza uma conta."""
        data = conta.to_dict()
        self.salvar_conta(
            email=data["email"],
            senha=data["senha"],
            id_perfil=data.get("id_perfil"),
            proxy=data.get("proxy"),
            email_backup=data.get("email_backup"),
            senha_email_backup=data.get("senha_email_backup")
        )
        return conta

    def salvar_varias(self, contas: Sequence[Conta]) -> Sequence[Conta]:
        """Salva várias contas."""
        try:
            with self._get_connection() as conn:
                sql = """
                INSERT INTO contas (email, senha, id_perfil, proxy, email_backup, senha_email_backup) 
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    senha = excluded.senha,
                    id_perfil = COALESCE(excluded.id_perfil, contas.id_perfil),
                    proxy = COALESCE(excluded.proxy, contas.proxy),
                    email_backup = COALESCE(excluded.email_backup, contas.email_backup),
                    senha_email_backup = COALESCE(excluded.senha_email_backup, contas.senha_email_backup);
                """
                params = [
                    (
                        c.email, 
                        c.senha, 
                        c.id_perfil, 
                        c.proxy.uri if c.proxy else None,
                        c.email_backup,
                        c.senha_email_backup
                    ) 
                    for c in contas
                ]
                conn.executemany(sql, params)
                conn.commit()
            return contas
        except Exception as e:
            raise wrap_exception(e, DatabaseException, "Erro ao salvar várias contas em lote")

    def remover(self, conta: Conta) -> None:
        """Remove uma conta."""
        sql = "DELETE FROM contas WHERE email = ?"
        try:
            with self._get_connection() as conn:
                conn.execute(sql, (conta.email,))
                conn.commit()
        except Exception as e:
            raise wrap_exception(e, DatabaseException, "Erro ao remover conta", email=conta.email)

    # IDatabaseRepository implementation

    def adicionar_registro_farm(self, email: str, pontos: int) -> Mapping[str, Any] | None:
        """Adiciona ou atualiza registro de farm."""
        self.logger.debug(f"Atualizando pontos para {email}: {pontos}")
        
        # Como o email é PK, este método assume que a conta já existe ou cria uma parcial
        # Idealmente, o import deve criar a conta completa primeiro.
        # Aqui faremos um UPDATE se existir, ou INSERT se não (upsert simplificado)
        
        # Mudança: Usar UPDATE direto para evitar erro de constraint (senha NOT NULL) no INSERT
        # Como o registro deve existir (foi carregado antes), o UPDATE deve funcionar.
        
        sql = """
        UPDATE contas 
        SET pontos = ?, ultima_farm = datetime('now')
        WHERE email = ?;
        """
        
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(sql, (pontos, email))
                # Verifica se atualizou algo
                if cursor.rowcount == 0:
                    self.logger.aviso(f"Tentativa de atualizar farm para conta inexistente: {email}")
                
                conn.commit()
                
                # Retorna o registro atualizado
                return self.consultar_conta(email)
        except Exception as e:
            self.logger.erro(f"Erro ao registrar farm SQLite: {e}")
            return None

    def consultar_conta(self, email: str) -> Mapping[str, Any] | None:
        """Consulta conta pelo email."""
        sql = "SELECT * FROM contas WHERE email = ?"
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(sql, (email,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
        except Exception as e:
            self.logger.erro(f"Erro ao consultar conta SQLite: {e}")
            return None

    def listar_contas(self) -> Sequence[Mapping[str, Any]]:
        """Lista todas as contas."""
        sql = "SELECT * FROM contas"
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(sql)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            self.logger.erro(f"Erro ao listar contas SQLite: {e}")
            return []

    def salvar_conta(self, email: str, senha: str, id_perfil: str = None, proxy: str = None, email_backup: str = None, senha_email_backup: str = None) -> Mapping[str, Any] | None:
        """
        Salva ou atualiza uma conta completa (usado pelo importador).
        """
        sql = """
        INSERT INTO contas (email, senha, id_perfil, proxy, email_backup, senha_email_backup) 
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
            senha = excluded.senha,
            id_perfil = COALESCE(excluded.id_perfil, contas.id_perfil),
            proxy = COALESCE(excluded.proxy, contas.proxy),
            email_backup = COALESCE(excluded.email_backup, contas.email_backup),
            senha_email_backup = COALESCE(excluded.senha_email_backup, contas.senha_email_backup);
        """
        try:
            with self._get_connection() as conn:
                conn.execute(sql, (email, senha, id_perfil, proxy, email_backup, senha_email_backup))
                conn.commit()
                return self.consultar_conta(email)
        except Exception as e:
             # Se falhar na constraint de PK, tentamos update explícito se for o caso, 
             # mas o ON CONFLICT deve resolver.
            raise wrap_exception(e, DatabaseException, "Erro ao salvar conta no SQLite", email=email)
