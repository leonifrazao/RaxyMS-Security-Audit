# Models – Modelos ORM Compartilhados

Este diretório reúne os modelos declarativos utilizados pela aplicação. Eles são baseados em SQLAlchemy e compartilham uma infraestrutura comum para serialização e definição de chaves.

## Arquivos principais

| Arquivo             | Descrição                                                                 |
|---------------------|----------------------------------------------------------------------------|
| `modelo_base.py`    | Define `BaseDeclarativa` (classe base SQLAlchemy) e `ModeloBase`, fornecendo `to_dict()`, `chaves_definidas()` e validação de chaves. |
| `conta_modelo.py`   | Implementa `ModeloConta`, utilizado pela automação (`id`, `email`, `senha`, `id_perfil`, `pontos`). O campo `pontos` pode ser alimentado com `APIRecompensas.extrair_pontos_disponiveis`. |
| `__init__.py`       | Reexporta símbolos (`ModeloBase`, `BaseDeclarativa`, `ModeloConta`) para facilitar imports. |

## Estrutura de um modelo

Todos os modelos devem herdar de `ModeloBase` e declarar:

1. `__tablename__`: nome da tabela no banco.
2. `CHAVES`: tupla com os campos que identificam unicamente a instância (para operações por key).
3. Colunas usando `mapped_column` (ou colunas tradicionais do SQLAlchemy).

Exemplo completo:

```python
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from Models.modelo_base import ModeloBase

class ModeloConta(ModeloBase):
    __tablename__ = "contas"
    CHAVES = ("email",)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    senha: Mapped[str] = mapped_column(String(255), nullable=False)
    id_perfil: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pontos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

## Convertendo e acessando dados

- `to_dict()`: retorna um dicionário com as colunas mapeadas.
- `chaves_definidas()`: devolve apenas as chaves (`CHAVES`) preenchidas, útil para buscas.

```python
conta = ModeloConta(email="user@example.com", senha="abc")
dados = conta.to_dict()  # {"id": None, "email": ..., ...}
chaves = conta.chaves_definidas()  # {"email": "user@example.com"}
```

## Criando novos modelos

1. Crie um novo arquivo (ex.: `pedido_modelo.py`).
2. Declare a classe herdando de `ModeloBase`.
3. Registre o modelo em `Models/__init__.py` para exportação.
4. Execute os testes para garantir compatibilidade.

## Integração com BaseModelos

Os modelos aqui definidos são consumidos por `BaseModelos` (`src/base_modelos.py`), que oferece métodos de CRUD, buscas por key/ID, remoções em massa e registro de métodos personalizados.
Integre-os com as respostas da API utilizando os helpers de `APIRecompensas` para converter JSON em valores persistíveis.

Para utilizar:
```python
from src import BaseModelos
from Models import ModeloConta

base = BaseModelos()
conta = base.inserir_ou_atualizar(ModeloConta(email="user@example.com", senha="123"))
```

## Boas práticas

- Utilize tipos e restrições (`nullable=False`, `unique=True`) para evitar inconsistências.
- Se precisar de chaves compostas, ajuste `CHAVES` e lembre-se de adaptar a PK para múltiplas colunas.
- Considere adicionar campos de auditoria (timestamps) conforme necessário.

Consulte [`README.md`](../README.md) para entender como os modelos se encaixam na arquitetura geral.
