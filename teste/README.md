# FastPipe

**FastPipe** é uma biblioteca Python leve e elegante para criação de serviços de comunicação inter-processos usando o sistema de arquivos como meio de transporte. Permite executar funções Python remotamente através de pipes simples e eficientes, ideal para arquiteturas de microserviços e processamento distribuído.

## 🚀 Características Principais

- **Comunicação via Sistema de Arquivos**: Usa arquivos JSON para troca de mensagens entre processos
- **API Simples e Intuitiva**: Decoradores fáceis de usar para definir endpoints
- **Suporte a Async/Await**: Compatível com funções síncronas e assíncronas
- **Modo Daemon**: Execução de serviços em background
- **Registro Automático**: Descoberta automática de serviços
- **Tolerante a Falhas**: Tratamento robusto de erros e timeouts
- **Zero Dependências Externas**: Usa apenas bibliotecas padrão do Python

## 📋 Requisitos

- Python 3.7+
- Nenhuma dependência externa

## 🛠 Instalação

```bash
# Assumindo que você tem o código fonte
pip install -e .
```

## 🎯 Uso Básico

### 1. Criando um Serviço

```python
import fastpipe as fp
import asyncio

@fp.create("meu-servico").daemon()
class MeuServico:
    def __init__(self, nome: str = "Serviço"):
        self.nome = nome
    
    @fp.home
    def home(self) -> str:
        return f"Bem-vindo ao {self.nome}!"
    
    @fp.get
    def status(self) -> dict:
        return {"status": "ativo", "nome": self.nome}
    
    @fp.post
    async def processar(self, dados: list) -> str:
        await asyncio.sleep(0.1)  # Simula processamento
        return f"Processados {len(dados)} itens"

# Inicia o serviço em background
handle = fp.run()
```

### 2. Conectando ao Serviço

```python
import fastpipe as fp

# Conecta ao serviço
client = fp.connect("meu-servico", nome="Meu Serviço Personalizado")

# Chama endpoints remotos
print(client.home())              # "Bem-vindo ao Meu Serviço Personalizado!"
print(client.status())            # {"status": "ativo", "nome": "Meu Serviço Personalizado"}
print(client.processar([1,2,3]))  # "Processados 3 itens"

# Lista endpoints disponíveis
print(client.endpoints())         # ['home', 'status', 'processar']
```

## 📚 Documentação Completa

### Decoradores de Endpoint

FastPipe oferece vários decoradores para marcar métodos como endpoints remotos:

#### `@fp.home`
Marca um método como endpoint "home" (página inicial do serviço):

```python
@fp.home
def home(self) -> str:
    return "Página inicial do serviço"
```

#### `@fp.get`
Marca um método como endpoint de leitura (o nome do endpoint será o nome do método):

```python
@fp.get
def obter_dados(self) -> dict:
    return {"dados": "exemplo"}
```

#### `@fp.post`
Marca um método como endpoint de escrita (o nome do endpoint será o nome do método):

```python
@fp.post
def salvar_dados(self, dados: dict) -> str:
    # Processa dados
    return "Dados salvos com sucesso"
```

#### `@fp.endpoint(name)`
Marca um método com um nome de endpoint personalizado:

```python
@fp.endpoint("processar-pedido")
def processar_pedido_especial(self, pedido: dict) -> dict:
    return {"resultado": "processado"}
```

### Criação de Serviços

#### Serviço Básico
```python
import fastpipe as fp

# Cria um serviço simples
service = fp.create("exemplo-basico")

@service.register()
def saudacao(nome: str) -> str:
    return f"Olá, {nome}!"
```

#### Serviço com Classe (Recomendado)
```python
@fp.create("exemplo-classe").daemon()
class ExemploServico:
    def __init__(self, configuracao: dict = None):
        self.config = configuracao or {}
    
    @fp.get
    def configuracao(self) -> dict:
        return self.config
    
    @fp.post
    def atualizar_config(self, nova_config: dict) -> str:
        self.config.update(nova_config)
        return "Configuração atualizada"
```

### Execução de Serviços

#### Modo Daemon (Recomendado)
```python
# Executa em background
handle = fp.run("nome-do-servico")

# Verifica se está rodando
print(f"Serviço rodando: {handle.is_running()}")
print(f"PID: {handle.pid}")

# Para o serviço
handle.stop()
```

#### Modo Bloqueante
```python
# Executa e bloqueia a thread atual
handle = fp.run("nome-do-servico", wait=True)
```

#### Controle Manual
```python
service = fp.create("manual-service")

# Inicia o servidor
service.start()

# Faz o que precisa...

# Para o servidor
service.stop()
```

### Conexão com Serviços

#### Conexão Básica
```python
client = fp.connect("nome-do-servico")
```

#### Conexão com Argumentos do Construtor
```python
# Passa argumentos para o construtor da classe do serviço
client = fp.connect(
    "nome-do-servico",
    "arg1", "arg2",                    # argumentos posicionais
    timeout=10.0,                      # timeout de conexão
    poll_interval=0.01,                # intervalo de polling
    kwarg1="valor1", kwarg2="valor2"   # argumentos nomeados
)
```

#### Timeouts e Configurações
```python
client = fp.connect(
    "nome-do-servico",
    timeout=30.0,        # Timeout para chamadas remotas (padrão: 5.0s)
    poll_interval=0.05   # Intervalo de verificação de resposta (padrão: 0.01s)
)
```

### Tratamento de Erros

FastPipe define várias exceções específicas:

```python
from fastpipe import (
    FastPipeError,           # Erro base
    ServiceNotFound,         # Serviço não encontrado
    ServiceAlreadyExists,    # Serviço já existe e está ativo
    RemoteExecutionError     # Erro na execução remota
)

try:
    client = fp.connect("servico-inexistente")
except ServiceNotFound as e:
    print(f"Serviço não encontrado: {e}")

try:
    result = client.metodo_que_falha()
except RemoteExecutionError as e:
    print(f"Erro na execução remota: {e}")
```

### Configuração do Ambiente

#### Diretório do FastPipe
Por padrão, FastPipe usa `.fastpipe/` no diretório atual. Você pode personalizar:

```bash
export FASTPIPE_HOME=/caminho/personalizado
```

#### Estrutura de Diretórios
```
.fastpipe/
├── registry/          # Registro de serviços ativos
│   └── servico1.json
├── services/          # Workspace dos serviços
│   └── servico1/
│       ├── requests/  # Requisições pendentes
│       └── responses/ # Respostas dos serviços
```

## 🔧 Exemplos Avançados

### Serviço de Processamento de Dados
```python
import asyncio
import fastpipe as fp
from typing import List, Dict, Any

@fp.create("processador-dados").daemon()
class ProcessadorDados:
    def __init__(self, workers: int = 4):
        self.workers = workers
        self.cache = {}
    
    @fp.home
    def info(self) -> Dict[str, Any]:
        return {
            "servico": "Processador de Dados",
            "workers": self.workers,
            "cache_size": len(self.cache)
        }
    
    @fp.get
    def cache_stats(self) -> Dict[str, int]:
        return {"itens": len(self.cache)}
    
    @fp.post
    async def processar_lote(self, dados: List[Dict]) -> Dict[str, Any]:
        """Processa um lote de dados de forma assíncrona."""
        inicio = time.time()
        
        # Simula processamento assíncrono
        tasks = [self._processar_item(item) for item in dados]
        resultados = await asyncio.gather(*tasks)
        
        fim = time.time()
        
        return {
            "processados": len(resultados),
            "tempo": fim - inicio,
            "resultados": resultados
        }
    
    @fp.endpoint("limpar-cache")
    def limpar_cache(self) -> str:
        tamanho = len(self.cache)
        self.cache.clear()
        return f"Cache limpo. {tamanho} itens removidos."
    
    async def _processar_item(self, item: Dict) -> Dict:
        # Simula processamento
        await asyncio.sleep(0.01)
        return {"id": item.get("id"), "processado": True}

# Inicia o serviço
if __name__ == "__main__":
    handle = fp.run("processador-dados")
    print(f"Processador iniciado (PID: {handle.pid})")
    
    try:
        handle.join()  # Aguarda até ser interrompido
    except KeyboardInterrupt:
        handle.stop()
        print("Processador encerrado.")
```

### Cliente para o Processador
```python
import fastpipe as fp

def main():
    # Conecta ao processador
    processador = fp.connect("processador-dados", workers=8)
    
    # Obtém informações do serviço
    print("Info do serviço:", processador.info())
    
    # Processa dados
    dados = [{"id": i, "valor": i * 2} for i in range(100)]
    resultado = processador.processar_lote(dados)
    
    print(f"Processamento concluído: {resultado}")
    
    # Verifica cache
    print("Cache stats:", processador.cache_stats())
    
    # Limpa cache
    print(processador.limpar_cache())

if __name__ == "__main__":
    main()
```

### Serviço com Estado Compartilhado
```python
import threading
import fastpipe as fp
from typing import Any, Dict

@fp.create("contador-compartilhado").daemon()
class ContadorCompartilhado:
    def __init__(self, valor_inicial: int = 0):
        self._valor = valor_inicial
        self._lock = threading.Lock()
        self._historico = []
    
    @fp.get
    def valor(self) -> int:
        with self._lock:
            return self._valor
    
    @fp.post
    def incrementar(self, quantidade: int = 1) -> Dict[str, Any]:
        with self._lock:
            valor_anterior = self._valor
            self._valor += quantidade
            self._historico.append({
                "operacao": "incremento",
                "quantidade": quantidade,
                "valor_anterior": valor_anterior,
                "valor_atual": self._valor
            })
            return {
                "valor_anterior": valor_anterior,
                "valor_atual": self._valor,
                "incremento": quantidade
            }
    
    @fp.post
    def decrementar(self, quantidade: int = 1) -> Dict[str, Any]:
        return self.incrementar(-quantidade)
    
    @fp.post
    def reset(self, novo_valor: int = 0) -> str:
        with self._lock:
            valor_anterior = self._valor
            self._valor = novo_valor
            self._historico.append({
                "operacao": "reset",
                "valor_anterior": valor_anterior,
                "valor_atual": novo_valor
            })
            return f"Contador resetado de {valor_anterior} para {novo_valor}"
    
    @fp.get
    def historico(self) -> list:
        with self._lock:
            return list(self._historico)
```

## 🐛 Debugging e Troubleshooting

### Verificação de Serviços Ativos
```python
import os
from pathlib import Path

def listar_servicos_ativos():
    fastpipe_home = Path(os.environ.get("FASTPIPE_HOME", ".fastpipe"))
    registry_dir = fastpipe_home / "registry"
    
    if not registry_dir.exists():
        print("Nenhum serviço registrado")
        return
    
    for service_file in registry_dir.glob("*.json"):
        print(f"Serviço: {service_file.stem}")
```

### Limpeza Manual
```python
import shutil
from pathlib import Path

def limpar_fastpipe():
    """Remove todos os dados do FastPipe (use com cuidado!)"""
    fastpipe_home = Path(".fastpipe")
    if fastpipe_home.exists():
        shutil.rmtree(fastpipe_home)
        print("Dados do FastPipe removidos")
```

### Logs e Debugging
```python
import logging

# Ativa logs detalhados
logging.basicConfig(level=logging.DEBUG)

# Ou configure apenas para FastPipe
logger = logging.getLogger("fastpipe")
logger.setLevel(logging.DEBUG)
```

## 🔒 Considerações de Segurança

- **FastPipe usa o sistema de arquivos local** - não é adequado para comunicação entre máquinas diferentes
- **Sem autenticação** - qualquer processo com acesso ao diretório pode chamar os serviços
- **Serialização JSON** - apenas tipos serializáveis em JSON são suportados
- **Execução local** - serviços rodam com as mesmas permissões do processo que os criou

## ⚡ Performance

### Otimizações
- Use `poll_interval` menor para menor latência (mais uso de CPU)
- Use `poll_interval` maior para menor uso de CPU (maior latência)
- Agrupe múltiplas operações em uma única chamada quando possível
- Cache resultados no lado do cliente quando apropriado

### Limitações
- **Latência**: Comunicação via arquivos tem overhead maior que sockets
- **Throughput**: Limitado pela velocidade do sistema de arquivos
- **Escalabilidade**: Melhor para poucos serviços com comunicação ocasional

## 🤝 Contribuição

FastPipe é um projeto open-source. Contribuições são bem-vindas!

### Desenvolvimento
```bash
# Clone o repositório
git clone <repository-url>
cd fastpipe

# Instale em modo desenvolvimento
pip install -e .

# Execute os testes
python -m pytest

# Execute os exemplos
python basic_usage.py
```

## 📄 Licença

[Inserir informações de licença aqui]

## 🙋 Suporte

Para dúvidas, problemas ou sugestões:
- Abra uma issue no repositório
- Consulte a documentação dos exemplos
- Verifique os logs para debugging

---

**FastPipe** - Comunicação inter-processos simples e eficiente para Python 🐍✨