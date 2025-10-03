"""Implementação do repositório de banco de dados utilizando Supabase."""

from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Any, Mapping

from dotenv import load_dotenv
from supabase import create_client, Client

from interfaces.repositories.IDatabaseRepository import IDatabaseRepository
from services.logging_service import log

# Carrega variáveis de ambiente de um arquivo .env, se existir
load_dotenv()

class SupabaseRepository(IDatabaseRepository):
    """Implementa a interface de repositório de banco de dados com a biblioteca Supabase."""

    def __init__(self) -> None:
        """
        Inicializa o cliente Supabase.
        """
        url: str | None = os.environ.get("SUPABASE_URL")
        key: str | None = os.environ.get("SUPABASE_KEY")

        if not url or not key:
            log.critico("As variáveis de ambiente SUPABASE_URL e SUPABASE_KEY são necessárias.")
            raise ValueError("Credenciais do Supabase não encontradas no ambiente.")

        try:
            self.supabase: Client = create_client(url, key)
            log.info("Cliente Supabase inicializado com sucesso.")
        except Exception as e:
            log.critico("Falha ao criar o cliente Supabase.", erro=e)
            raise

    def adicionar_registro_farm(self, email: str, pontos: int) -> Mapping[str, Any] | None:
        """
        Adiciona ou atualiza o registro de uma conta na tabela 'contas'.
        """
        logger = log.com_contexto(conta=email, pontos=pontos)
        logger.info("Adicionando/atualizando registro de farm no banco de dados.")

        try:
            timestamp_atual = datetime.now(timezone.utc).isoformat()
            data_para_enviar = {
                "email": email,
                "pontos": pontos,
                "ultima_farm": timestamp_atual,
            }

            # --- ALTERAÇÃO AQUI ---
            # Adicionamos 'returning="minimal"' para dizer à API para não retornar os dados,
            # apenas executar a ação. Isso evita o erro de resposta vazia.
            response = (
                self.supabase.table("contas")
                .upsert(
                    data_para_enviar,
                    on_conflict="email",  # <--- Esta é a parte mágica
                    returning="minimal"
                )
                .execute()
            )

            # A resposta com 'returning=minimal' não tem 'data' nem 'error' em caso de sucesso
            # A biblioteca pode retornar um erro em 'response.error' se houver um problema real.
            # Vamos verificar se existe um erro real na resposta.
            if hasattr(response, 'error') and response.error:
                logger.erro("Erro retornado pelo Supabase ao registrar farm.", erro=response.error)
                return None
            
            # Se não houve erro, a operação foi um sucesso.
            logger.sucesso("Registro de farm salvo no banco de dados com sucesso.")
            # Como não pedimos dados de volta, retornamos o que enviamos como confirmação.
            return data_para_enviar

        except Exception as e:
            logger.critico("Exceção inesperada ao tentar registrar farm no Supabase.", erro=e)
            return None

    def consultar_conta(self, email: str) -> Mapping[str, Any] | None:
        """
        Consulta uma conta na tabela 'contas' pelo email.
        """
        logger = log.com_contexto(conta=email)
        logger.info("Consultando conta no banco de dados.")
        
        try:
            data, error = (
                self.supabase.table("contas")
                .select("*")
                .eq("email", email)
                .limit(1)
                .execute()
            )

            if error:
                logger.erro("Erro retornado pelo Supabase ao consultar conta.", erro=error)
                return None

            if data and data[1]:
                logger.info("Conta encontrada no banco de dados.")
                return data[1][0]
            
            logger.info("Nenhuma conta encontrada com o email fornecido.")
            return None

        except Exception as e:
            logger.critico("Exceção inesperada ao consultar conta no Supabase.", erro=e)
            return None