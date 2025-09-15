# Documentação Geral – Projeto Raxy

Bem-vindo à documentação oficial do Raxy! Este guia consolida todas as informações relevantes sobre a automação de contas Microsoft Rewards, estrutura do código, processos de execução e contribuição.

> **Resumo rápido:** Raxy é uma aplicação Python 3.11+ que roda automações com botasaurus, organiza logs avançados, gerencia perfis de navegador e mantém dados com SQLAlchemy/SQLite – tudo escrito em português para facilitar a manutenção por equipes pt-BR.

## Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura de Pastas](#arquitetura-de-pastas)
3. [Pré-requisitos](#pré-requisitos)
4. [Configuração do Ambiente](#configuração-do-ambiente)
5. [Fluxo Principal](#fluxo-principal)
6. [Logging e Observabilidade](#logging-e-observabilidade)
7. [Persistência e Modelos](#persistência-e-modelos)
8. [Testes Automatizados](#testes-automatizados)
9. [Extensões e Contribuição](#extensões-e-contribuição)
10. [Referências Rápidas](#referências-rápidas)

## Visão Geral

- **Objetivo:** automatizar login e navegação no Microsoft Rewards para múltiplas contas, com rastreabilidade das ações e persistência opcional dos dados.
- **Linguagem:** Python 3.11+
- **Principais dependências:** `rich`, `botasaurus`, `sqlalchemy`, `random-user-agent`.
- **Documentação complementar:**
  - [`raxy/README.md`](raxy/README.md) – resumo operacional do pacote principal.
  - [`raxy/src/README.md`](raxy/src/README.md) – detalhes dos módulos core.
  - [`raxy/Models/README.md`](raxy/Models/README.md) – instruções para criar modelos ORM.
  - [`raxy/tests/README.md`](raxy/tests/README.md) – guia de testes automatizados.

## Arquitetura de Pastas

```
.
├── DOCUMENTACAO.md        # Este arquivo
├── raxy/                  # Código-fonte principal
│   ├── main.py            # Executor em lote
│   ├── Models/            # Modelos SQLAlchemy
│   ├── src/               # Autenticação, logging, base de dados
│   └── tests/             # Testes unitários
├── users.txt              # Exemplo de arquivo de contas (fora do .git)
└── shell.nix / .venv ...  # Configurações de ambiente (opcionais)
```

## Pré-requisitos

- Python 3.11 ou superior
- pip (ou outra ferramenta de gerenciamento de pacotes)
- Navegador/driver compatível com botasaurus (Chrome/Edge baseado em Chromium)
- Opcional: virtualenv/Poetry para isolamento

### Dependências Python

```bash
pip install rich botasaurus sqlalchemy random-user-agent
```

## Configuração do Ambiente

1. Clone o repositório.
2. Crie um ambiente virtual (opcional).
3. Instale as dependências listadas acima.
4. Prepare o arquivo `users.txt` com entradas `email:senha` (uma por linha).
5. Ajuste variáveis de ambiente conforme necessário:
   - `USERS_FILE`: caminho do arquivo de contas.
   - `ACTIONS`: sequências de ações (ex.: `login`, `rewards`).
   - Variáveis de logging (`LOG_LEVEL`, `LOG_FILE`, `LOG_COLOR`, etc.).

## Fluxo Principal

- `raxy/main.py` implementa `ExecutorEmLote`, responsável por:
  1. Ler contas de `users.txt`.
  2. Criar contexto de logging por conta.
  3. Executar `AutenticadorRewards.executar` (login) e `NavegadorRecompensas.abrir_pagina` (rewards) conforme ações configuradas.
  4. Reportar erros sem interromper as demais contas.

O fluxo pode ser estendido para incluir novas ações (ex.: coleta de pontos, scraping). Basta adicionar métodos em `ExecutorEmLote` e gerenciar via `ACTIONS`.

## Logging e Observabilidade

- `src/logging.py` configura `log`, com níveis personalizados (`sucesso`, `aviso`, etc.) e contextos.
- Uso recomendado:
  ```python
  from src.logging import log
  log.info("Processo iniciado", contas=10)
  with log.etapa("Login", conta="user@example.com"):
      ...
  ```
- Variáveis de ambiente controlam output em arquivo, cores e tracebacks Rich.

## Persistência e Modelos

- `Models/` define a camada ORM: `ModeloBase`, `ModeloConta` e quaisquer modelos personalizados.
- `src/base_modelos.py` disponibiliza `BaseModelos`, que cria automaticamente `dados.db` (SQLite) e oferece operações avançadas:
  - CRUD tradicional (`obter`, `obter_por_key`, `inserir_ou_atualizar`, `delete`).
  - Operações por ID (`obter_por_id`, `atualizar_por_id`, `deletar_por_id`).
  - Remoções em massa com predicado (`remover_por_key`).
  - Registro de métodos personalizados.

Exemplo:
```python
from src import BaseModelos
from Models import ModeloConta

base = BaseModelos()
base.inserir_ou_atualizar(ModeloConta(email="user@example.com", senha="123"))
base.remover_por_key(ModeloConta(email="user@example.com", senha="qualquer"), predicado=lambda c: c.pontos > 1000)
```

## Testes Automatizados

- Baseados em `unittest`, localizados em `raxy/tests/`.
- Para rodar toda a suíte:
  ```bash
  cd raxy
  python -m unittest discover tests
  ```
- Os testes que dependem de SQLAlchemy são executados com banco em memória.
- Consulte o README específico (`raxy/tests/README.md`) para detalhes e boas práticas.

## Extensões e Contribuição

1. **Novos fluxos de automação**: adicione métodos no `ExecutorEmLote` e exponha-os via `ACTIONS`.
2. **Enriquecimento do logging**: use contextos (`log.com_contexto`) para metadados adicionais, escreva em arquivos (`LOG_FILE`).
3. **Modelos adicionais**: crie classes em `Models/`, reexporte-as e utilize via `BaseModelos`.
4. **Persistência alternativa**: substitua o SQLite por outro banco passando `url_banco` (ex.: `postgresql+psycopg://...`).
5. **Testes**: crie cenários de regressão sempre que adicionar funcionalidades novas.

## Referências Rápidas

- **Documentação botasaurus:** <https://github.com/0theco/botasaurus>
- **Rich para logging:** <https://rich.readthedocs.io>
- **SQLAlchemy ORM:** <https://docs.sqlalchemy.org/en/20/orm>
- **random-user-agent:** <https://pypi.org/project/random-user-agent/>

> Dica: ao publicar no GitHub, mantenha este `DOCUMENTACAO.md` e os READMEs sincronizados para garantir que qualquer colaborador comece entendendo a arquitetura completa.

Bom trabalho e boas automações!
