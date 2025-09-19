# core – Núcleo da Aplicação

Este diretório concentra os módulos responsáveis pela automação completa:

- Autenticação e gerenciamento de sessão (Botasaurus + SQLAlchemy).
- Navegação controlada e camada de API para o Rewards.
- Logging opinativo com Rich em português.
- Perfis de navegador e helpers de configuração reutilizáveis.
- Carregamento de contas a partir de arquivos simples.
- Persistência com `BaseModelos` (SQLAlchemy/SQLite por padrão).

## Visão geral dos módulos

| Arquivo             | Descrição                                                                                          |
|---------------------|------------------------------------------------------------------------------------------------------|
| `auth.py`           | Classe `AutenticadorRewards` com validação de email/senha, interação DOM e logging contextual.       |
| `browser.py`        | `NavegadorRecompensas` abre a página do Bing Rewards com configurações opinativas de navegador.      |
| `rewards_api.py`    | `APIRecompensas` reutiliza `GerenciadorSolicitacoesRewards` e oferece utilitários de parsing JSON.   |
| `session.py`        | Captura cookies/tokens e expõe `ClienteSolicitacoesRewards` com tratamento de erros estruturado.     |
| `profiles.py`       | `GerenciadorPerfil` garante perfis botasaurus, gera user-agents e monta argumentos de navegador.     |
| `accounts.py`       | Funções para carregar contas (`carregar_contas`) e dataclass `Conta` com `email/senha/id_perfil`.    |
| `logging.py`        | Framework de logging em português (`log`, contextos, etapas e integração com Rich).                  |
| `storage.py`        | Handler `BaseModelos` (CRUD, operações por ID, remoções filtradas, métodos personalizados).          |
| `config.py`         | Defaults do decorator `@browser`, URL base do Rewards e `ExecutorConfig` com leitura de ambiente.    |
| `helpers/`          | Funções utilitárias compartilhadas (parsing de variáveis de ambiente, tokens de request).            |
| `__init__.py`       | Reexporta a interface pública para consumo externo.                                                 |

## AutenticadorRewards

Principais métodos:
- `AutenticadorRewards.validar_credenciais(email, senha)`: normaliza dados e lança `CredenciaisInvalidas` quando necessário.
- `AutenticadorRewards.executar(...)`: fluxo completo de login, reuso de sessão e logging contextual.

Personalizações:
- Aceita `profile`, `add_arguments` e `data` (`email`, `senha`) como parâmetros.
- Adiciona métodos de contexto (`registro`) para logar cada passo.

## Navegação e API do Rewards

- `NavegadorRecompensas.abrir_pagina(...)`: habilita modo humano e abre `REWARDS_BASE_URL` (configurável via `REWARDS_BASE_URL`).
- `APIRecompensas.obter_pontos(...)`: reutiliza um `GerenciadorSolicitacoesRewards` para capturar os pontos brutos da API.
- `APIRecompensas.extrair_pontos_disponiveis(dados)`: percorre qualquer resposta JSON e devolve `availablePoints` como `int`.
- `APIRecompensas.obter_recompensas(...)`: devolve o JSON das recompensas disponíveis.
- `APIRecompensas.contar_recompensas(dados)`: identifica coleções de itens (`catalogItems`, `items`, listas com `price`).

## GerenciadorPerfil

- `garantir_agente_usuario(perfil)`: cria/obtém perfil botasaurus focando em user agent Edge.
- `argumentos_agente_usuario(perfil)`: retorna argumentos `--user-agent=...` para o navegador.

## Helpers de configuração

O pacote `helpers` contém funções utilitárias para leitura consistente de variáveis de ambiente:

- `get_env_bool`, `get_env_int`, `get_env_list`, `get_env_value` padronizam parsing e fallback.
- Reutilize essas funções ao adicionar novos comportamentos configuráveis.

## Carregamento de contas

- `carregar_contas(path)`: lê arquivos `email:senha`, ignora linhas inválidas/comentadas e cria objetos `Conta`.
- `Conta` oferece campos `email`, `senha`, `id_perfil` (derivada automaticamente).

## Logging opinativo

- `log`: instância global com níveis `debug`, `info`, `sucesso`, `aviso`, `erro`, `critico`.
- `log.etapa(...)`: context manager que loga início/sucesso/falha automaticamente.
- Configuração via variáveis: `LOG_LEVEL`, `LOG_FILE`, `LOG_COLOR`, `LOG_RICH_TRACEBACK`, etc.

Exemplo:
```python
from raxy import log

log.info("Inicio da sincronização")
with log.etapa("Login", conta="user@example.com"):
    ...
```

## BaseModelos

`BaseModelos` concentra o CRUD da aplicação e expõe:

- `obter(Modelo)`, `obter_por_key(modelo)`, `inserir_ou_atualizar(modelo)`, `delete(modelo)`.
- `obter_por_id`, `atualizar_por_id`, `deletar_por_id`.
- `remover_por_key` (com predicado opcional).
- Registro de métodos personalizados via `metodos_personalizados`.

Para ambientes sem SQLAlchemy instalado, importe `BaseModelos` através de `raxy` ou `raxy.core`; em tempo de importação é emitido erro amigável caso a dependência esteja ausente.
