# Documentação Geral – Projeto Raxy

Bem-vindo à documentação oficial do Raxy! Este guia consolida todas as informações relevantes sobre a automação de contas Microsoft Rewards, estrutura do código, processos de execução e contribuição.

> **Resumo rápido:** Raxy é uma aplicação Python 3.11+ que roda automações com botasaurus, organiza logs avançados, gerencia perfis de navegador e mantém dados com SQLAlchemy/SQLite – tudo escrito em português para facilitar a manutenção por equipes pt-BR. O executor suporta processamento paralelo opcional e expõe utilidades para extrair pontos e recompensas diretamente das respostas do Rewards.

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
  - [`raxy/DOCUMENTACAO.md`](raxy/DOCUMENTACAO.md) – panorama operacional do pacote principal.
  - [`raxy/core/README.md`](raxy/core/README.md) – detalhes dos módulos core.
  - [`raxy/Models/README_models.md`](raxy/Models/README_models.md) – instruções para criar modelos ORM.
  - [`raxy/tests/README_tests.md`](raxy/tests/README_tests.md) – guia de testes automatizados.

## Arquitetura de Pastas

```
.
├── DOCUMENTACAO.md        # Guia operacional da automação
├── raxy/                  # Código-fonte principal
│   ├── main.py            # Entrada CLI enxuta
│   ├── core/              # Autenticação, APIs, perfis, config e persistência
│   ├── services/          # Orquestração e fluxos de alto nível
│   ├── Models/            # Modelos SQLAlchemy
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
5. Ajuste variáveis de ambiente conforme necessário (todas são lidas e normalizadas pelo `ExecutorConfig` e helpers de ambiente):
   - `USERS_FILE`: caminho do arquivo de contas.
   - `ACTIONS`: sequências de ações (ex.: `login`, `rewards`).
   - `MAX_WORKERS` / `RAXY_MAX_WORKERS`: limite de paralelismo.
   - `REWARDS_BASE_URL`: sobrescreve a URL padrão `https://rewards.bing.com`.
   - `RAXY_API_INTERACTIVE` e `RAXY_SOLICITACOES_INTERATIVAS`: controlam prompts sonoros/interativos.
   - Variáveis de logging (`LOG_LEVEL`, `LOG_FILE`, `LOG_COLOR`, etc.).

## Fluxo Principal

- `raxy/services/executor.py` define `ExecutorEmLote`, responsável por:
  1. Ler contas de `users.txt`.
  2. Criar contexto de logging por conta.
  3. Executar `AutenticadorRewards.executar` (login), `NavegadorRecompensas.abrir_pagina` (rewards) e chamadas de API conforme `ACTIONS`.
  4. Orquestrar as contas sequencialmente ou em paralelo via `ThreadPoolExecutor` (configurado com `ExecutorConfig.max_workers`).
  5. Reportar erros sem interromper as demais contas.

Utilidades pós-processamento residem em `APIRecompensas` (`extrair_pontos_disponiveis`, `contar_recompensas`) para reduzir duplicação ao interpretar os retornos JSON.

O fluxo pode ser estendido para incluir novas ações (ex.: coleta de pontos, scraping). Basta adicionar métodos em `ExecutorEmLote` e gerenciar via `ACTIONS`.

## Logging e Observabilidade

- `raxy/core/logging.py` configura `log`, com níveis personalizados (`sucesso`, `aviso`, etc.) e contextos.
- Uso recomendado:
  ```python
  from raxy import log
  log.info("Processo iniciado", contas=10)
  with log.etapa("Login", conta="user@example.com"):
      ...
  ```
- Variáveis de ambiente controlam output em arquivo, cores e tracebacks Rich.

## Persistência e Modelos

- `Models/` define a camada ORM: `ModeloBase`, `ModeloConta` e quaisquer modelos personalizados.
- `raxy/core/storage.py` disponibiliza `BaseModelos`, que cria automaticamente `dados.db` (SQLite) e oferece operações avançadas:
  - CRUD tradicional (`obter`, `obter_por_key`, `inserir_ou_atualizar`, `delete`).
  - Operações por ID (`obter_por_id`, `atualizar_por_id`, `deletar_por_id`).
  - Remoções em massa com predicado (`remover_por_key`).
  - Registro de métodos personalizados.

Exemplo:
```python
from raxy import BaseModelos
from Models import ModeloConta

base = BaseModelos()
base.inserir_ou_atualizar(ModeloConta(email="user@example.com", senha="123"))
base.remover_por_key(ModeloConta(email="user@example.com", senha="qualquer"), predicado=lambda c: c.pontos > 1000)
```

## Testes Automatizados

- Baseados em `unittest`, localizados em `raxy/tests/`.
- Para rodar toda a suíte (a maioria dos testes evita chamadas reais ao navegador):
  ```bash
  cd raxy
  python -m unittest discover tests
  ```
- Testes que dependem do botasaurus exigem ambiente capaz de abrir portas locais; em ambientes restritos, execute-os manualmente.
- Os testes que dependem de SQLAlchemy são executados com banco em memória.
- Consulte o README específico (`raxy/tests/README.md`) para detalhes e boas práticas.

## Extensões e Contribuição

1. **Novos fluxos de automação**: adicione métodos no `ExecutorEmLote` e exponha-os via `ACTIONS`. Se a ação incluir consultas HTTP, avalie mover parsing para `APIRecompensas`.
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
