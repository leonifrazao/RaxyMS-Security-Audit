# tests – Suíte de Testes Unitários

Este diretório abriga a suíte de testes automatizados construída com `unittest`. Os testes cobrem as principais camadas da aplicação e servem como documentação viva para o comportamento esperado.

## Estrutura

| Arquivo             | Cobertura principal                                                                    |
|---------------------|-----------------------------------------------------------------------------------------|
| `test_login.py`     | Valida `AutenticadorRewards.validar_credenciais` e cenários negativos (email/senha).    |
| `test_executor.py`  | Testa normalização de ações, leitura de arquivo e integração parcial do executor (incluindo helpers). |
| `test_utils.py`     | Usa `unittest.mock` para garantir que `GerenciadorPerfil` interage corretamente com botasaurus. |
| `test_base_modelos.py` | Exercita `BaseModelos` (CRUD, buscas por key/ID, remoção com predicado, métodos customizados). |

## Executando a suíte

```bash
cd raxy
python -m unittest discover tests
```

> **Observações:**
> - Os testes de `base_modelos` requerem `sqlalchemy`. Com ele instalado, toda a suíte é executada; do contrário, os testes correspondentes são ignorados automaticamente.
> - Alguns testes de alto nível podem instanciar botasaurus; em ambientes sem permissão para abrir portas locais, execute-os manualmente.

## Boas práticas ao contribuir

1. **Crie um teste por comportamento:** ao adicionar funcionalidades novas, inclua testes positivos e negativos.
2. **Utilize mocks** para isolar dependências externas (navegador, rede). Veja `test_utils.py` como referência.
3. **Valide helpers de parsing** (`APIRecompensas`) com respostas artificiais antes de integrá-los ao executor.
4. **Evite efeitos colaterais:** use bancos em memória (`sqlite:///:memory:`) ou arquivos temporários (`tempfile`) para manter o ambiente limpo.
5. **Rode os testes antes de abrir PRs** para garantir regressões zero.

## Exemplo de novo teste

```python
from unittest import TestCase
from src.logging import log

class TestLogging(TestCase):
    def test_log_sucesso(self):
        with self.assertLogs("rich", level="INFO"):
            log.sucesso("Operação concluída")
```

## Relatórios e cobertura

Para integrar com ferramentas como `coverage.py`:

```bash
coverage run -m unittest discover tests
coverage html
```

## Recursos adicionais

- Documentação oficial do `unittest`: <https://docs.python.org/3/library/unittest.html>
- Documentação do `unittest.mock`: <https://docs.python.org/3/library/unittest.mock.html>

Consulte [`README.md`](../README.md) para ver como os testes se encaixam na arquitetura geral do projeto.
