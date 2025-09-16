# Raxy – Automação Microsoft Rewards

Raxy é um utilitário completo que orquestra múltiplas contas do Microsoft Rewards com foco em observabilidade, robustez e extensibilidade. Ele integra automação via botasaurus, logging rico com Rich, gerenciamento de perfis de navegador, persistência com SQLAlchemy e uma suíte de testes automatizados.

## Principais recursos

- **Execução em lote** com controle por variáveis de ambiente (`USERS_FILE`, `ACTIONS`).
- **Logging opinativo em português** com Rich, contextos e níveis customizados (`log`, `configurar_logging`).
- **Gerenciamento de perfis/User-Agent** dedicado para otimizar pontuação no Rewards.
- **Autenticação resiliente** (validação de email/senha, tratamentos de DOM e sugestões de falhas).
- **Camada de dados extensível** com SQLAlchemy (`BaseModelos`, `ModeloConta`) e suporte a métodos customizados.
- **Testes automatizados** cobrindo cada camada (`unittest`).

## Estrutura do projeto

```
raxy/
├── main.py              # Ponto de entrada (ExecutorEmLote)
├── README.md            # Este guia
├── Models/              # Modelos ORM
├── src/                 # Componentes principais
├── tests/               # Suíte de testes
└── dados.db             # Banco SQLite criado automaticamente
```

### Models
Contém a base declarativa (`ModeloBase`) e modelos concretos como `ModeloConta`, prontos para uso com SQLAlchemy. Consulte [`Models/README_models.md`](Models/README_models.md) para detalhes de extensão.

### src
Módulos responsáveis por autenticação, navegação, logging, carregamento de contas e pela `BaseModelos`. Veja [`src/README_src.md`](src/README_src.md) para um tour completo.

### tests
Suíte de testes unitários cobrindo autenticação, executor, utilitários e camada de dados. Instruções completas em [`tests/README_tests.md`](tests/README_tests.md).

## Preparação do ambiente

1. **Crie e ative um ambiente virtual (opcional):**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   .venv\\Scripts\\activate   # Windows
   ```
2. **Instale dependências principais:**
   ```bash
   pip install rich botasaurus sqlalchemy random-user-agent
   ```
   Ajuste conforme sua stack. `sqlalchemy` é obrigatório para a camada de dados.

## Execução

1. Prepare um arquivo `users.txt` (ou use `USERS_FILE` para alterar o caminho):
   ```
   usuario1@example.com:senha1
   usuario2@example.com:senha2
   ```
2. Defina as ações desejadas (`login`, `rewards`, ou ambas separadas por vírgula).
3. Execute:
   ```bash
   cd raxy
   USERS_FILE=../users.txt ACTIONS="login,rewards" python main.py
   ```

## Logging e observabilidade

- `src/logging.py` configura uma instância global `log` com cores, contexto dinâmico e suporte a arquivo (`LOG_FILE`, `LOG_LEVEL`, etc.).
- Mensagens são emitidas em português; use `log.com_contexto(...)` para adicionar metadados por conta.

## Persistência com BaseModelos

- Por padrão, um SQLite `dados.db` é criado na primeira utilização (ajuste com `BaseModelos(url_banco=...)`).
- Métodos disponíveis:
  - `obter`, `obter_por_key`, `inserir_ou_atualizar`, `delete`
  - `obter_por_id`, `atualizar_por_id`, `deletar_por_id`
  - `remover_por_key` (com predicado opcional)
  - Métodos customizados via `metodos_personalizados`.

Exemplo rápido:
```python
from src import BaseModelos
from Models import ModeloConta

base = BaseModelos()
conta = base.inserir_ou_atualizar(ModeloConta(email="user@example.com", senha="123"))
base.atualizar_por_id(conta.id, ModeloConta(email=conta.email, senha="nova"))
```

## Testes

Para executar todos os testes (requer `sqlalchemy`):
```bash
cd raxy
python -m unittest discover tests
```

Os testes incluem mocks para isolamento e cobrem os principais caminhos críticos. Amplie a suíte conforme adicionar novos módulos.

## Personalização e próximos passos

- **Novos modelos:** derive de `ModeloBase`, defina `__tablename__`, `CHAVES` e colunas via SQLAlchemy.
- **Métodos customizados:** passe um dicionário `metodos_personalizados` ao instanciar `BaseModelos`.
- **Integração externa:** exponha `BaseModelos` via API, CLI ou UI conforme necessário.
- **Observabilidade:** configure `LOG_FILE` para persistir logs ou integre com ferramentas externas (ELK, Loki etc.).

Ficou com dúvida? Consulte também [`README.md`](../README.md) na raiz para uma visão consolidada do repositório.
