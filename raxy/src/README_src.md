# src – Núcleo da Aplicação

Este diretório concentra os módulos responsáveis pela automação completa:

- Autenticação e navegação (botasaurus + SQLAlchemy).
- Logging em português com Rich.
- Gerenciamento de perfis de navegador e user-agent.
- Carregamento de contas a partir de arquivos simples.
- Handler de persistência (`BaseModelos`) com operações avançadas.

## Visão geral dos módulos

| Arquivo             | Descrição                                                                                          |
|---------------------|------------------------------------------------------------------------------------------------------|
| `autenticacao.py`   | Classe `AutenticadorRewards` com validação de email/senha, interação DOM e logging contextual.      |
| `navegacao.py`      | `NavegadorRecompensas` abre a página do Bing Rewards com human-mode e suporte a reuso de driver.    |
| `utilitarios.py`    | `GerenciadorPerfil` garante perfis botasaurus, gera user-agents e monta argumentos de navegador.    |
| `contas.py`         | Funções para carregar contas (`carregar_contas`) e dataclass `Conta` com `email/senha/id_perfil`.   |
| `logging.py`        | Framework de logging em português (`log`, `configurar_logging`, contextos, etapas e arquivo).       |
| `base_modelos.py`   | Handler `BaseModelos` (CRUD, operações por ID, remoções filtradas, métodos personalizados).         |
| `config.py`         | Configurações compartilhadas do decorador `@browser` do botasaurus.                                  |
| `__init__.py`       | Reexporta a interface pública (AutenticadorRewards, NavegadorRecompensas, GerenciadorPerfil, etc.). |

## AutenticadorRewards

Principais métodos:
- `AutenticadorRewards.validar_credenciais(email, senha)`: normaliza dados e lança `CredenciaisInvalidas` quando necessário.
- `AutenticadorRewards.executar(...)`: fluxo completo de login, reuso de sessão e logging contextual.
- Alias `login(...)` mantém compatibilidade com chamadas antigas.

Personalizações:
- Aceita `profile`, `add_arguments` e `data` (`email`, `senha`) como parâmetros.
- Adiciona métodos de contexto (`registro`) para logar cada passo.

## NavegadorRecompensas

- `abrir_pagina(driver, dados=None)`: habilita modo humano e abre `https://rewards.bing.com`.
- Decorador `@browser` com `reuse_driver=True` para reutilização de sessão.
- Alias `goto_rewards_page` para compatibilidade com código pré-existente.

## GerenciadorPerfil

- `garantir_agente_usuario(perfil)`: cria/obtém perfil botasaurus focando em user agent Edge.
- `argumentos_agente_usuario(perfil)`: retorna argumentos `--user-agent=...` para o navegador.

## Carregamento de contas

- `carregar_contas(path)`: lê arquivos `email:senha`, ignora linhas inválidas/comentadas e cria objetos `Conta`.
- `Conta` oferece campos `email`, `senha`, `id_perfil` (derivada automaticamente).

## Logging opinativo

- `log`: instância global com níveis `debug`, `info`, `sucesso`, `aviso`, `erro`, `critico`.
- `log.etapa(...)`: context manager que loga início/sucesso/falha automaticamente.
- Configuração via variáveis: `LOG_LEVEL`, `LOG_FILE`, `LOG_COLOR`, `LOG_RICH_TRACEBACK`, etc.

Exemplo:
```python
from src.logging import log

log.info("Inicio da sincronização")
with log.etapa("Login", conta="user@example.com"):
    ...
```

## BaseModelos

`BaseModelos` concentra o CRUD da aplicação e expõe:

- `obter(Modelo)`, `obter_por_key(modelo)`, `inserir_ou_atualizar(modelo)`, `delete(modelo)`.
- `obter_por_id(id, Modelo)`, `atualizar_por_id(id, modelo)`, `deletar_por_id(id, Modelo)`.
- `remover_por_key(modelo, predicado=None)`: remove vários registros que batam com as chaves (predicado opcional para refinamento).
- `metodos_personalizados={"nome": func}`: injeta métodos adicionais no handler (ex.: `aumentar_pontos`).

Banco de dados:
- Se nenhum `url_banco` for informado, cria `dados.db` (SQLite) automaticamente.
- Para ambientes de teste/CI, passe `url_banco="sqlite:///:memory:"`.

Exemplo:
```python
from src import BaseModelos
from Models import ModeloConta

base = BaseModelos()
conta = base.inserir_ou_atualizar(ModeloConta(email="user@example.com", senha="123"))
base.remover_por_key(ModeloConta(email="user@example.com", senha="qualquer"))
```

## Interface Pública (`__init__.py`)

Importe componentes diretamente:
```python
from src import (
    AutenticadorRewards,
    NavegadorRecompensas,
    GerenciadorPerfil,
    BaseModelos,
    Conta,
    carregar_contas,
)
```

## Boas práticas

- Centralize todo acesso à camada de dados em `BaseModelos` para manter consistência.
- Use `GerenciadorPerfil.argumentos_agente_usuario` em qualquer fluxo botasaurus.
- Sempre capture exceções em etapas críticas (como o `ExecutorEmLote` faz) e reporte via `log`.

Para uma visão arquitetural completa, confira [`README.md`](../README.md).
