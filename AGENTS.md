# Repository Guidelines

## Project Structure & Module Organization
- `raxy/services/executor.py` concentra o orquestrador; `raxy/core/` reúne autenticação, APIs, configuração e helpers reutilizáveis.
- `raxy/Models/` mantém os modelos SQLAlchemy; documente adições em `README_models.md` e exponha-as via `__init__.py` quando necessário.
- `raxy/tests/` hospeda a suíte `unittest` e `raxy/requests/` guarda payloads simulados; na raiz, use `requirements.txt`, `shell.nix` e `users.txt` como suportes locais (sem credenciais reais).

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` prepara o ambiente Python 3.11+.
- `pip install -r requirements.txt` instala dependências principais; registre extras (coverage, lint) antes de cobrá-los em CI.
- `USERS_FILE=../users.txt ACTIONS="login,rewards" python main.py` executa o fluxo a partir de `raxy/`; prefira variáveis de ambiente a argumentos fixos.
- `python -m unittest discover tests` cobre a suíte; adicione `coverage run -m unittest discover tests` somente quando precisar de métricas.

## Coding Style & Naming Conventions
- Indente com 4 espaços, mantenha funções em `snake_case`, classes em `CamelCase` e APIs públicas com tipagem explícita.
- Preserve identificadores, docstrings e logs em português; evite `print`, reutilize `raxy.log` e seus contextos.
- Prefira `dataclass(slots=True)` para contêineres simples e utilize os helpers de `raxy/core/helpers` ao lidar com variáveis de ambiente.

## Testing Guidelines
- Nomeie arquivos `raxy/tests/test_<modulo>.py` (ex.: `raxy/core/config.py` → `test_config.py`).
- Empregue `unittest.mock` para isolar botasaurus ou HTTP e use `sqlite:///:memory:` em cenários de banco.
- Adicione skips condicionais a testes que exigem navegador e atualize `raxy/tests/README_tests.md` quando o escopo mudar.

## Commit & Pull Request Guidelines
- Siga Conventional Commits (`feat:`, `fix:`, `refactor:`) com assunto minúsculo e até 72 caracteres.
- Descreva impactos no corpo, relacione issues e destaque novos env vars ou artefatos sensíveis (`users.txt`, perfis).
- Antes do review, execute `python -m unittest discover tests`; compartilhe variações relevantes de cobertura quando alterar fluxos críticos.

## Security & Configuration Tips
- Nunca versione dados reais de contas; compartilhe apenas exemplos sanitizados.
- Documente valores padrão ao criar novas variáveis de ambiente e prefira `.env` ignorado pelo git para segredos locais.
