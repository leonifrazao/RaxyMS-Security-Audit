"""
Testes Completos do Event Bus - Sistema Raxy

Este arquivo contém todos os testes de eventos:
1. Teste Básico do Event Bus (Redis Pub/Sub auto-start)
2. Teste de Eventos de Proxy
3. Teste de Eventos de Session/Account
4. Teste de Eventos de Rewards
5. Teste Completo Integrado

Execute:
    python raxy_project/tests/test_event_bus.py
    python raxy_project/tests/test_event_bus.py --test=basic
    python raxy_project/tests/test_event_bus.py --test=proxy
    python raxy_project/tests/test_event_bus.py --test=session
    python raxy_project/tests/test_event_bus.py --test=rewards
    python raxy_project/tests/test_event_bus.py --test=all
"""

import sys
import time
from raxy.container import get_container
from raxy.domain.accounts import Conta
from raxy.domain.events import (
    AccountLoggedIn,
    AccountLoggedOut,
    RewardsCollected,
    ProxyRotated,
    SessionStarted,
    SessionEnded,
    TaskCompleted,
    TaskFailed,
)


# ============================================================================
# TESTE 1: Event Bus Básico
# ============================================================================

def test_01_event_bus_basic():
    """Teste básico do Event Bus com eventos simples."""
    
    print("\n" + "="*70)
    print("🧪 TESTE 1: Event Bus Básico")
    print("="*70)
    
    # 1. Inicializa
    print("\n[1/4] 🚀 Inicializando Event Bus...")
    container = get_container()
    event_bus = container.event_bus()
    
    if not event_bus:
        print("❌ Event Bus não está habilitado")
        return False
    
    if not event_bus.is_running():
        event_bus.start()
        time.sleep(2)
    
    print("✅ Event Bus iniciado!")
    
    # 2. Registra handlers
    print("\n[2/4] 📝 Registrando handlers...")
    
    events_received = []
    
    def on_account_login(data):
        events_received.append(("account.logged_in", data))
        print(f"  ✅ CONTA LOGADA: {data.get('email')}")
    
    def on_rewards(data):
        events_received.append(("rewards.collected", data))
        print(f"  💰 RECOMPENSAS: +{data.get('points_gained')} pontos")
    
    def on_proxy(data):
        events_received.append(("proxy.rotated", data))
        print(f"  🔄 PROXY ROTACIONADA")
    
    def on_session(data):
        events_received.append(("session.started", data))
        print(f"  🎬 SESSÃO INICIADA: {data.get('session_id')}")
    
    event_bus.subscribe("account.logged_in", on_account_login)
    event_bus.subscribe("rewards.collected", on_rewards)
    event_bus.subscribe("proxy.rotated", on_proxy)
    event_bus.subscribe("session.started", on_session)
    
    time.sleep(1)
    print("✅ 4 handlers registrados")
    
    # 3. Publica eventos
    print("\n[3/4] 📤 Publicando eventos de teste...")
    
    login_event = AccountLoggedIn(
        account_id="test@example.com",
        email="test@example.com",
        profile_id="profile_001",
        proxy_id="proxy_us_01",
        market="US"
    )
    event_bus.publish("account.logged_in", login_event.to_dict())
    time.sleep(0.5)
    
    rewards_event = RewardsCollected(
        account_id="test@example.com",
        points_before=1000,
        points_after=1150,
        points_gained=150,
        tasks_completed=5,
        tasks_failed=0
    )
    event_bus.publish("rewards.collected", rewards_event.to_dict())
    time.sleep(0.5)
    
    proxy_event = ProxyRotated(
        old_proxy_id="proxy_us_01",
        new_proxy_id="proxy_us_02",
        old_proxy_url="http://proxy1.com:8080",
        new_proxy_url="http://proxy2.com:8080",
        reason="Manual rotation"
    )
    event_bus.publish("proxy.rotated", proxy_event.to_dict())
    time.sleep(0.5)
    
    session_event = SessionStarted(
        session_id="session_test_123",
        account_id="test@example.com",
        proxy_id="proxy_us_02",
        user_agent="Mozilla/5.0..."
    )
    event_bus.publish("session.started", session_event.to_dict())
    time.sleep(0.5)
    
    # 4. Valida
    print("\n[4/4] ✅ Validando...")
    success = len(events_received) == 4
    
    if success:
        print(f"✅ Todos os 4 eventos foram recebidos!")
    else:
        print(f"❌ Esperado 4 eventos, recebido {len(events_received)}")
    
    print("\n" + "="*70)
    return success


# ============================================================================
# TESTE 2: Eventos de Proxy
# ============================================================================

def test_02_proxy_events():
    """Teste específico de eventos de Proxy."""
    
    print("\n" + "="*70)
    print("🧪 TESTE 2: Eventos de Proxy")
    print("="*70)
    
    container = get_container()
    event_bus = container.event_bus()
    
    if not event_bus or not event_bus.is_running():
        event_bus.start()
        time.sleep(2)
    
    events_received = []
    
    def on_tested_success(data):
        events_received.append(("success", data))
        print(f"  ✅ Proxy testada: {data.get('proxy_id')} - {data.get('ping_ms')}ms")
    
    def on_tested_failed(data):
        events_received.append(("failed", data))
        print(f"  ❌ Proxy falhou: {data.get('proxy_id')}")
    
    def on_rotated(data):
        events_received.append(("rotated", data))
        print(f"  🔄 Rotação: {data.get('old_proxy_id')} → {data.get('new_proxy_id')}")
    
    event_bus.subscribe("proxy.tested.success", on_tested_success)
    event_bus.subscribe("proxy.tested.failed", on_tested_failed)
    event_bus.subscribe("proxy.rotated", on_rotated)
    time.sleep(1)
    
    print("\n📤 Simulando testes de proxy...")
    
    # Proxy com sucesso
    event_bus.publish("proxy.tested.success", {
        "proxy_id": "proxy_us_01",
        "proxy_url": "vmess://...",
        "country": "US",
        "ping_ms": 45.2,
        "ip": "192.168.1.1",
    })
    time.sleep(0.3)
    
    # Proxy com falha
    event_bus.publish("proxy.tested.failed", {
        "proxy_id": "proxy_br_02",
        "proxy_url": "vmess://...",
        "error": "Connection timeout",
    })
    time.sleep(0.3)
    
    # Rotação
    event_bus.publish("proxy.rotated", {
        "bridge_id": 0,
        "old_proxy_id": "proxy_us_01",
        "new_proxy_id": "proxy_us_03",
        "old_proxy_url": "http://proxy1.com:8080",
        "new_proxy_url": "http://proxy3.com:8080",
        "port": 54000,
        "reason": "Manual rotation",
    })
    time.sleep(0.5)
    
    success = len(events_received) == 3
    print(f"\n{'✅' if success else '❌'} Eventos recebidos: {len(events_received)}/3")
    print("="*70)
    return success


# ============================================================================
# TESTE 3: Eventos de Session/Account
# ============================================================================

def test_03_session_events():
    """Teste específico de eventos de Session e Account."""
    
    print("\n" + "="*70)
    print("🧪 TESTE 3: Eventos de Session/Account")
    print("="*70)
    
    container = get_container()
    event_bus = container.event_bus()
    
    if not event_bus or not event_bus.is_running():
        event_bus.start()
        time.sleep(2)
    
    events_received = []
    conta = Conta(email="test@example.com", senha="test", id_perfil="profile_001")
    
    def on_session_started(data):
        events_received.append(("session.started", data))
        print(f"  🎬 Sessão iniciada: {data.get('session_id')}")
    
    def on_session_ended(data):
        events_received.append(("session.ended", data))
        print(f"  🛑 Sessão encerrada: {data.get('duration_seconds')}s")
    
    def on_session_error(data):
        events_received.append(("session.error", data))
        print(f"  ❌ Erro: {data.get('error_type')}")
    
    def on_logged_in(data):
        events_received.append(("logged_in", data))
        print(f"  ✅ Login: {data.get('email')}")
    
    def on_logged_out(data):
        events_received.append(("logged_out", data))
        print(f"  👋 Logout: {data.get('email')}")
    
    event_bus.subscribe("session.started", on_session_started)
    event_bus.subscribe("session.ended", on_session_ended)
    event_bus.subscribe("session.error", on_session_error)
    event_bus.subscribe("account.logged_in", on_logged_in)
    event_bus.subscribe("account.logged_out", on_logged_out)
    time.sleep(1)
    
    print("\n📤 Simulando ciclo de sessão...")
    
    session_id = "session_test_1234567890"
    
    # Início
    event_bus.publish("session.started", {
        "session_id": session_id,
        "account_id": conta.email,
        "proxy_id": "proxy_us_01",
        "user_agent": "Mozilla/5.0...",
    })
    time.sleep(0.3)
    
    # Login
    event_bus.publish("account.logged_in", {
        "account_id": conta.email,
        "email": conta.email,
        "profile_id": conta.id_perfil,
        "proxy_id": "proxy_us_01",
        "market": "US",
    })
    time.sleep(0.5)
    
    # Logout
    event_bus.publish("account.logged_out", {
        "account_id": conta.email,
        "email": conta.email,
        "reason": "Session closed",
    })
    time.sleep(0.3)
    
    # Fim
    event_bus.publish("session.ended", {
        "session_id": session_id,
        "account_id": conta.email,
        "duration_seconds": 15.7,
        "reason": "Normal closure",
    })
    time.sleep(0.3)
    
    # Erro
    event_bus.publish("session.error", {
        "session_id": "session_error_test",
        "account_id": conta.email,
        "error_type": "LoginException",
        "error_message": "Invalid credentials",
        "is_recoverable": False,
    })
    time.sleep(0.5)
    
    success = len(events_received) == 5
    print(f"\n{'✅' if success else '❌'} Eventos recebidos: {len(events_received)}/5")
    print("="*70)
    return success


# ============================================================================
# TESTE 4: Eventos de Rewards
# ============================================================================

def test_04_rewards_events():
    """Teste específico de eventos de Rewards."""
    
    print("\n" + "="*70)
    print("🧪 TESTE 4: Eventos de Rewards")
    print("="*70)
    
    container = get_container()
    event_bus = container.event_bus()
    
    if not event_bus or not event_bus.is_running():
        event_bus.start()
        time.sleep(2)
    
    events_received = []
    conta = Conta(email="test@example.com", senha="test", id_perfil="profile_001")
    
    def on_points(data):
        events_received.append(("points", data))
        print(f"  📊 Pontos: {data.get('points')}")
    
    def on_collected(data):
        events_received.append(("collected", data))
        print(f"  💰 Coletadas: {data.get('tasks_completed')}/{data.get('total_tasks')}")
    
    def on_task_completed(data):
        events_received.append(("task.completed", data))
        print(f"  ✅ Tarefa: {data.get('task_id')} (+{data.get('points_earned')} pts)")
    
    def on_task_failed(data):
        events_received.append(("task.failed", data))
        print(f"  ❌ Falhou: {data.get('task_id')}")
    
    event_bus.subscribe("rewards.points.fetched", on_points)
    event_bus.subscribe("rewards.collected", on_collected)
    event_bus.subscribe("task.completed", on_task_completed)
    event_bus.subscribe("task.failed", on_task_failed)
    time.sleep(1)
    
    print("\n📤 Simulando coleta de rewards...")
    
    # Pontos iniciais
    event_bus.publish("rewards.points.fetched", {
        "account_id": conta.email,
        "points": 1500,
    })
    time.sleep(0.3)
    
    # Tarefas completadas
    for i in range(3):
        event_bus.publish("task.completed", {
            "account_id": conta.email,
            "task_id": f"task_{i+1}",
            "task_type": "daily_search",
            "points_earned": 10,
        })
        time.sleep(0.2)
    
    # Tarefa falhou
    event_bus.publish("task.failed", {
        "account_id": conta.email,
        "task_id": "task_4",
        "task_type": "quiz",
        "error_message": "Timeout",
        "retry_count": 0,
    })
    time.sleep(0.3)
    
    # Resumo
    event_bus.publish("rewards.collected", {
        "account_id": conta.email,
        "tasks_completed": 3,
        "tasks_failed": 1,
        "total_tasks": 4,
        "daily_sets_count": 1,
        "more_promotions_count": 0,
    })
    time.sleep(0.3)
    
    # Pontos finais
    event_bus.publish("rewards.points.fetched", {
        "account_id": conta.email,
        "points": 1530,
    })
    time.sleep(0.5)
    
    success = len(events_received) == 7  # 2 points + 3 completed + 1 failed + 1 collected
    print(f"\n{'✅' if success else '❌'} Eventos recebidos: {len(events_received)}/7")
    print("="*70)
    return success


# ============================================================================
# TESTE 5: Teste Completo Integrado (Original)
# ============================================================================


def test_event_bus_complete():
    """Teste completo do Event Bus com todos os eventos."""
    
    print("\n" + "="*70)
    print("🧪 TESTE COMPLETO DO EVENT BUS - RAXY")
    print("="*70)
    
    # 1. Inicializa Event Bus
    print("\n[1/6] 🚀 Inicializando Event Bus...")
    container = get_container()
    event_bus = container.event_bus()
    
    if not event_bus:
        print("❌ Event Bus não está habilitado no config.yaml")
        return False
    
    if not event_bus.is_running():
        event_bus.start()
        time.sleep(2)  # Aguarda Redis
    
    print("✅ Event Bus iniciado com sucesso!")
    
    # 2. Registra handlers
    print("\n[2/6] 📝 Registrando handlers de eventos...")
    
    events_received = {
        "proxy": [],
        "session": [],
        "account": [],
        "rewards": [],
        "task": [],
    }
    
    # Handlers de Proxy
    def on_proxy_tested_success(data):
        events_received["proxy"].append(("tested.success", data))
        print(f"  ✅ Proxy testada: {data.get('proxy_id')} - {data.get('ping_ms')}ms")
    
    def on_proxy_tested_failed(data):
        events_received["proxy"].append(("tested.failed", data))
        print(f"  ❌ Proxy falhou: {data.get('proxy_id')} - {data.get('error')}")
    
    def on_proxy_rotated(data):
        events_received["proxy"].append(("rotated", data))
        print(f"  🔄 Proxy rotacionada: {data.get('old_proxy_id')} → {data.get('new_proxy_id')}")
    
    # Handlers de Session
    def on_session_started(data):
        events_received["session"].append(("started", data))
        print(f"  🎬 Sessão iniciada: {data.get('session_id')}")
    
    def on_session_ended(data):
        events_received["session"].append(("ended", data))
        print(f"  🛑 Sessão encerrada: {data.get('session_id')} ({data.get('duration_seconds')}s)")
    
    def on_session_error(data):
        events_received["session"].append(("error", data))
        print(f"  ❌ Erro na sessão: {data.get('error_type')}")
    
    # Handlers de Account
    def on_account_logged_in(data):
        events_received["account"].append(("logged_in", data))
        print(f"  ✅ Login: {data.get('email')}")
    
    def on_account_logged_out(data):
        events_received["account"].append(("logged_out", data))
        print(f"  👋 Logout: {data.get('email')}")
    
    # Handlers de Rewards
    def on_points_fetched(data):
        events_received["rewards"].append(("points", data))
        print(f"  📊 Pontos: {data.get('points')}")
    
    def on_rewards_collected(data):
        events_received["rewards"].append(("collected", data))
        print(f"  💰 Recompensas: {data.get('tasks_completed')}/{data.get('total_tasks')} tarefas")
    
    def on_task_completed(data):
        events_received["task"].append(("completed", data))
        print(f"  ✅ Tarefa completada: {data.get('task_id')} (+{data.get('points_earned')} pts)")
    
    def on_task_failed(data):
        events_received["task"].append(("failed", data))
        print(f"  ❌ Tarefa falhou: {data.get('task_id')}")
    
    # Registra todos os handlers
    event_bus.subscribe("proxy.tested.success", on_proxy_tested_success)
    event_bus.subscribe("proxy.tested.failed", on_proxy_tested_failed)
    event_bus.subscribe("proxy.rotated", on_proxy_rotated)
    event_bus.subscribe("session.started", on_session_started)
    event_bus.subscribe("session.ended", on_session_ended)
    event_bus.subscribe("session.error", on_session_error)
    event_bus.subscribe("account.logged_in", on_account_logged_in)
    event_bus.subscribe("account.logged_out", on_account_logged_out)
    event_bus.subscribe("rewards.points.fetched", on_points_fetched)
    event_bus.subscribe("rewards.collected", on_rewards_collected)
    event_bus.subscribe("task.completed", on_task_completed)
    event_bus.subscribe("task.failed", on_task_failed)
    
    time.sleep(1)  # Aguarda handlers prontos
    print("✅ 12 handlers registrados")
    
    # 3. Testa eventos de Proxy
    print("\n[3/6] 🌐 Testando eventos de PROXY...")
    
    event_bus.publish("proxy.tested.success", {
        "proxy_id": "proxy_us_01",
        "proxy_url": "vmess://...",
        "country": "US",
        "ping_ms": 45.2,
        "ip": "192.168.1.1",
        "tested_at": "2025-10-24T00:30:00Z",
    })
    time.sleep(0.3)
    
    event_bus.publish("proxy.tested.failed", {
        "proxy_id": "proxy_br_02",
        "proxy_url": "vmess://...",
        "error": "Connection timeout",
        "tested_at": "2025-10-24T00:30:05Z",
    })
    time.sleep(0.3)
    
    event_bus.publish("proxy.rotated", {
        "bridge_id": 0,
        "old_proxy_id": "proxy_us_01",
        "new_proxy_id": "proxy_us_03",
        "old_proxy_url": "http://proxy1.com:8080",
        "new_proxy_url": "http://proxy3.com:8080",
        "port": 54000,
        "reason": "Manual rotation",
    })
    time.sleep(0.5)
    
    # 4. Testa eventos de Session/Account
    print("\n[4/6] 🔐 Testando eventos de SESSION e ACCOUNT...")
    
    session_id = "session_test_1234567890"
    conta = Conta(email="test@example.com", senha="test", id_perfil="profile_001")
    
    event_bus.publish("session.started", {
        "session_id": session_id,
        "account_id": conta.email,
        "proxy_id": "proxy_us_03",
        "user_agent": "Mozilla/5.0...",
    })
    time.sleep(0.3)
    
    event_bus.publish("account.logged_in", {
        "account_id": conta.email,
        "email": conta.email,
        "profile_id": conta.id_perfil,
        "proxy_id": "proxy_us_03",
        "market": "US",
    })
    time.sleep(0.3)
    
    # Simula uso da sessão
    time.sleep(0.5)
    
    event_bus.publish("account.logged_out", {
        "account_id": conta.email,
        "email": conta.email,
        "reason": "Session closed",
    })
    time.sleep(0.3)
    
    event_bus.publish("session.ended", {
        "session_id": session_id,
        "account_id": conta.email,
        "duration_seconds": 15.7,
        "reason": "Normal closure",
    })
    time.sleep(0.3)
    
    event_bus.publish("session.error", {
        "session_id": "session_error_test",
        "account_id": conta.email,
        "error_type": "LoginException",
        "error_message": "Invalid credentials",
        "is_recoverable": False,
    })
    time.sleep(0.5)
    
    # 5. Testa eventos de Rewards
    print("\n[5/6] 💰 Testando eventos de REWARDS...")
    
    event_bus.publish("rewards.points.fetched", {
        "account_id": conta.email,
        "points": 1500,
    })
    time.sleep(0.3)
    
    # Simula tarefas
    for i in range(3):
        event_bus.publish("task.completed", {
            "account_id": conta.email,
            "task_id": f"task_{i+1}",
            "task_type": "daily_search",
            "points_earned": 10,
        })
        time.sleep(0.2)
    
    event_bus.publish("task.failed", {
        "account_id": conta.email,
        "task_id": "task_4",
        "task_type": "quiz",
        "error_message": "Timeout",
        "retry_count": 0,
    })
    time.sleep(0.3)
    
    event_bus.publish("rewards.collected", {
        "account_id": conta.email,
        "tasks_completed": 3,
        "tasks_failed": 1,
        "total_tasks": 4,
        "daily_sets_count": 1,
        "more_promotions_count": 0,
    })
    time.sleep(0.3)
    
    event_bus.publish("rewards.points.fetched", {
        "account_id": conta.email,
        "points": 1530,
    })
    time.sleep(0.5)
    
    # 6. Valida resultados
    print("\n[6/6] 📊 Validando resultados...")
    
    total_events = sum(len(events) for events in events_received.values())
    
    print(f"\n✅ Total de eventos recebidos: {total_events}")
    print(f"   - Proxy: {len(events_received['proxy'])} eventos")
    print(f"   - Session: {len(events_received['session'])} eventos")
    print(f"   - Account: {len(events_received['account'])} eventos")
    print(f"   - Rewards: {len(events_received['rewards'])} eventos")
    print(f"   - Task: {len(events_received['task'])} eventos")
    
    # Verifica se todos os eventos esperados foram recebidos
    expected = {
        "proxy": 3,      # tested.success, tested.failed, rotated
        "session": 3,    # started, ended, error
        "account": 2,    # logged_in, logged_out
        "rewards": 3,    # points (2x), collected
        "task": 4,       # completed (3x), failed
    }
    
    success = True
    for category, count in expected.items():
        received = len(events_received[category])
        if received != count:
            print(f"   ❌ {category}: esperado {count}, recebido {received}")
            success = False
    
    print("\n" + "="*70)
    if success:
        print("🎉 TESTE COMPLETO: SUCESSO!")
        print("="*70)
        print("\n✨ Todos os 15 eventos foram publicados e recebidos corretamente!")
        print("✨ O Event Bus está funcionando perfeitamente!")
    else:
        print("❌ TESTE COMPLETO: FALHOU!")
        print("="*70)
        print("\n⚠️  Alguns eventos não foram recebidos corretamente.")
    
    print("\n")
    return success


def main():
    """Executa os testes conforme argumentos."""
    
    # Parse argumentos
    test_name = "all"
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.startswith("--test="):
            test_name = arg.split("=")[1]
    
    tests = {
        "basic": ("Teste Básico", test_01_event_bus_basic),
        "proxy": ("Eventos de Proxy", test_02_proxy_events),
        "session": ("Eventos de Session", test_03_session_events),
        "rewards": ("Eventos de Rewards", test_04_rewards_events),
        "complete": ("Teste Completo", test_event_bus_complete),
    }
    
    results = {}
    
    if test_name == "all":
        # Executa todos os testes
        print("\n" + "🧪"*35)
        print("EXECUTANDO TODOS OS TESTES DO EVENT BUS")
        print("🧪"*35)
        
        for key, (name, test_func) in tests.items():
            try:
                results[key] = test_func()
            except Exception as e:
                print(f"\n❌ Erro no teste {name}: {e}")
                results[key] = False
        
        # Resumo final
        print("\n" + "="*70)
        print("📊 RESUMO DOS TESTES")
        print("="*70)
        
        for key, (name, _) in tests.items():
            status = "✅ PASSOU" if results.get(key) else "❌ FALHOU"
            print(f"  {status} - {name}")
        
        total = len(results)
        passed = sum(1 for r in results.values() if r)
        
        print("\n" + "="*70)
        print(f"🎯 Total: {passed}/{total} testes passaram")
        print("="*70 + "\n")
        
        return all(results.values())
    
    elif test_name in tests:
        # Executa teste específico
        name, test_func = tests[test_name]
        print(f"\n🧪 Executando: {name}")
        try:
            return test_func()
        except Exception as e:
            print(f"\n❌ Erro: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    else:
        print(f"\n❌ Teste '{test_name}' não encontrado!")
        print("\nTestes disponíveis:")
        print("  --test=all       Executa todos os testes")
        for key, (name, _) in tests.items():
            print(f"  --test={key:12} {name}")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
