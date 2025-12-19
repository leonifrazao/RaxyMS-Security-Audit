# 🧪 Testes do Event Bus - Raxy

Testes completos do sistema de eventos Event-Driven do Raxy.

## 📋 Testes Disponíveis

### 1. **Teste Básico** (`test_01_event_bus_basic`)
Valida funcionamento básico do Event Bus:
- ✅ Auto-start do Redis
- ✅ Registro de handlers
- ✅ Publicação de eventos básicos
- ✅ Recebimento de eventos

**Eventos testados:** `account.logged_in`, `rewards.collected`, `proxy.rotated`, `session.started`

### 2. **Eventos de Proxy** (`test_02_proxy_events`)
Testa eventos do sistema de Proxy:
- ✅ `proxy.tested.success` - Proxy testada com sucesso
- ✅ `proxy.tested.failed` - Proxy falhou no teste
- ✅ `proxy.rotated` - Proxy rotacionada

### 3. **Eventos de Session/Account** (`test_03_session_events`)
Testa ciclo completo de sessão e conta:
- ✅ `session.started` - Início de sessão
- ✅ `account.logged_in` - Login de conta
- ✅ `account.logged_out` - Logout de conta
- ✅ `session.ended` - Fim de sessão
- ✅ `session.error` - Erro na sessão

### 4. **Eventos de Rewards** (`test_04_rewards_events`)
Testa sistema de recompensas completo:
- ✅ `rewards.points.fetched` - Pontos obtidos (2x)
- ✅ `task.completed` - Tarefas completadas (3x)
- ✅ `task.failed` - Tarefa falhou
- ✅ `rewards.collected` - Resumo de coleta

### 5. **Teste Completo** (`test_event_bus_complete`)
Teste integrado com todos os eventos do sistema (15 eventos no total).

## 🚀 Como Executar

### Executar todos os testes:
```bash
python raxy_project/tests/test_event_bus.py
# ou
python raxy_project/tests/test_event_bus.py --test=all
```

### Executar teste específico:
```bash
# Teste básico
python raxy_project/tests/test_event_bus.py --test=basic

# Eventos de Proxy
python raxy_project/tests/test_event_bus.py --test=proxy

# Eventos de Session
python raxy_project/tests/test_event_bus.py --test=session

# Eventos de Rewards
python raxy_project/tests/test_event_bus.py --test=rewards

# Teste completo integrado
python raxy_project/tests/test_event_bus.py --test=complete
```

## ✅ Resultado Esperado

### Sucesso:
```
🧪 TESTE 1: Event Bus Básico
==================================================
[1/4] 🚀 Inicializando Event Bus...
✅ Event Bus iniciado!

[2/4] 📝 Registrando handlers...
✅ 4 handlers registrados

[3/4] 📤 Publicando eventos de teste...
  ✅ CONTA LOGADA: test@example.com
  💰 RECOMPENSAS: +150 pontos
  🔄 PROXY ROTACIONADA
  🎬 SESSÃO INICIADA: session_test_123

[4/4] ✅ Validando...
✅ Todos os 4 eventos foram recebidos!
==================================================
```

### Resumo Final (todos os testes):
```
📊 RESUMO DOS TESTES
==================================================
  ✅ PASSOU - Teste Básico
  ✅ PASSOU - Eventos de Proxy
  ✅ PASSOU - Eventos de Session
  ✅ PASSOU - Eventos de Rewards
  ✅ PASSOU - Teste Completo
==================================================
🎯 Total: 5/5 testes passaram
==================================================
```

## 🔧 Pré-requisitos

1. **Redis** deve estar instalado (auto-start ativado)
2. **Event Bus** deve estar habilitado em `config.yaml`:
```yaml
events:
  enabled: true
  host: localhost
  port: 6379
  db: 0
  prefix: "raxy:events:"
```

3. **Dependências** instaladas:
```bash
nix-shell  # Redis já incluído
pip install redis
```

## 🐛 Troubleshooting

### Problema: Eventos não são recebidos
**Causa:** Race condition - handlers não prontos

**Solução:** Os testes já incluem `time.sleep()` adequados. Se persistir, aumente os delays.

### Problema: Redis não inicia
**Causa:** `redis-server` não encontrado

**Solução:**
```bash
# Usando nix-shell (recomendado)
nix-shell

# Ou instalação manual
sudo apt install redis-server
```

### Problema: Testes falham aleatoriamente
**Causa:** Thread de listener processando assincronamente

**Solução:** Normal para sistema assíncrono. Execute novamente. Se falhar consistentemente, há um bug real.

## 📊 Cobertura

- ✅ **Event Bus** - Redis Pub/Sub
- ✅ **Auto-start Redis** - Inicia automaticamente
- ✅ **Handlers** - Registro e processamento
- ✅ **Domain Events** - 11 tipos diferentes
- ✅ **Proxy Events** - 3 eventos
- ✅ **Session Events** - 3 eventos  
- ✅ **Account Events** - 2 eventos
- ✅ **Rewards Events** - 4 eventos
- ✅ **Integration** - Teste completo com 15 eventos

## 🎯 Próximos Passos

Após todos os testes passarem:

1. **Adicione testes unitários** para cada módulo
2. **Testes de integração** com conta real (opcional)
3. **Testes de performance** - latência e throughput
4. **Testes de carga** - múltiplos publishers/subscribers
5. **CI/CD** - Integrar no pipeline

## 📝 Notas

- Todos os testes são **não-destrutivos** - apenas simulam eventos
- **Nenhuma credencial real** é necessária
- Testes são **idempotentes** - podem ser executados múltiplas vezes
- **Thread-safe** - Redis Pub/Sub é thread-safe por design
