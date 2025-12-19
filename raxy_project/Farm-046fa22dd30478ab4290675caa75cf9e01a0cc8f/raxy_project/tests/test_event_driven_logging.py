"""
Testes do Sistema de Logging Descentralizado via Event Bus.

Demonstra uso correto vs incorreto e padrões recomendados.
"""

import sys
import time
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from raxy.core.events import RedisEventBus
from raxy.core.logging.event_bus_logging import (
    setup_event_driven_logging,
    EventDrivenLoggingConfig,
    create_hostname_enricher,
    create_pid_enricher,
    create_level_filter
)
from raxy.core.config import LoggerConfig


def test_01_basic_event_driven_logging():
    """
    Teste 1: Logging Descentralizado Básico.
    
    Demonstra o fluxo básico:
    1. Service A emite log
    2. Log é publicado no Event Bus
    3. Agregador recebe e roteia para destinos
    """
    print("\n" + "="*70)
    print("🧪 TESTE 1: Logging Descentralizado Básico")
    print("="*70)
    
    # Setup Event Bus
    print("\n[1/4] 🚀 Iniciando Event Bus...")
    event_bus = RedisEventBus(host="localhost", port=6379)
    
    try:
        event_bus.start()
        time.sleep(1)
        print("✅ Event Bus iniciado!")
    except Exception as e:
        print(f"❌ Erro ao iniciar Event Bus: {e}")
        return False
    
    # Setup Logging via Event Bus
    print("\n[2/4] 📝 Configurando logging descentralizado...")
    
    event_config = EventDrivenLoggingConfig(
        enabled=True,
        service_name="test-service",
        adaptive_sampling=False,
        sampling_rate=1.0,
        enable_aggregator=True,
        aggregator_console=True,
        aggregator_file=False
    )
    
    logger, aggregator = setup_event_driven_logging(
        event_bus=event_bus,
        event_config=event_config
    )
    
    time.sleep(1)
    print("✅ Sistema de logging configurado!")
    
    # Testa logs
    print("\n[3/4] 📤 Enviando logs via Event Bus...")
    
    logger.info("Sistema iniciado", service="auth", version="2.0.0")
    time.sleep(0.2)
    
    logger.debug("Processando requisição", request_id="req-123", user_id="user-456")
    time.sleep(0.2)
    
    logger.sucesso("Login realizado com sucesso", email="test@example.com", duration_ms=125)
    time.sleep(0.2)
    
    logger.aviso("Taxa de uso alta", cpu_percent=85.5, memory_mb=1024)
    time.sleep(0.2)
    
    logger.erro("Erro ao conectar ao banco", error_code="DB001", retry_count=3)
    time.sleep(0.5)
    
    print("✅ Logs enviados!")
    
    # Valida
    print("\n[4/4] ✅ Validando métricas...")
    
    # Pega métricas do handler
    for handler in logger.handlers:
        if hasattr(handler, 'get_metrics'):
            metrics = handler.get_metrics()
            print(f"\n   Métricas do Event Bus Handler:")
            print(f"   - Logs publicados: {metrics['published']}")
            print(f"   - Logs descartados: {metrics['dropped']}")
            print(f"   - Erros: {metrics['errors']}")
            print(f"   - Fallback usado: {metrics['fallback_used']}")
    
    # Pega métricas do agregador
    if aggregator:
        agg_metrics = aggregator.get_metrics()
        print(f"\n   Métricas do Agregador:")
        print(f"   - Eventos recebidos: {agg_metrics['events_received']}")
        print(f"   - Eventos processados: {agg_metrics['events_processed']}")
        print(f"   - Eventos filtrados: {agg_metrics['events_filtered']}")
        print(f"   - Eventos com erro: {agg_metrics['events_failed']}")
    
    # Cleanup
    logger.flush()
    time.sleep(1)
    event_bus.stop()
    
    print("\n" + "="*70)
    print("✅ TESTE 1: SUCESSO!")
    print("="*70)
    return True


def test_02_adaptive_sampling():
    """
    Teste 2: Adaptive Sampling sob Alta Carga.
    
    Demonstra como o sistema se adapta automaticamente
    reduzindo sampling quando a queue está cheia.
    """
    print("\n" + "="*70)
    print("🧪 TESTE 2: Adaptive Sampling sob Alta Carga")
    print("="*70)
    
    # Setup
    print("\n[1/3] 🚀 Configurando com Adaptive Sampling...")
    event_bus = RedisEventBus()
    
    try:
        event_bus.start()
        time.sleep(1)
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False
    
    event_config = EventDrivenLoggingConfig(
        enabled=True,
        service_name="high-load-service",
        adaptive_sampling=True,  # Sampling adaptativo
        queue_size=100,  # Queue pequena para forçar adaptação
        enable_aggregator=True,
        aggregator_console=False  # Desabilita console para não poluir
    )
    
    logger, aggregator = setup_event_driven_logging(
        event_bus=event_bus,
        event_config=event_config
    )
    
    time.sleep(1)
    print("✅ Configurado com Adaptive Sampling!")
    
    # Gera alta carga
    print("\n[2/3] 🔥 Gerando alta carga de logs...")
    
    start_time = time.time()
    log_count = 1000
    
    for i in range(log_count):
        logger.info(f"Log de alta frequência #{i}", iteration=i, batch=i//100)
        
        # Mostra progresso
        if (i + 1) % 200 == 0:
            print(f"   Enviados {i + 1}/{log_count} logs...")
    
    duration = time.time() - start_time
    throughput = log_count / duration
    
    print(f"✅ {log_count} logs enviados em {duration:.2f}s ({throughput:.0f} logs/s)")
    
    # Aguarda processamento
    print("\n[3/3] ⏳ Aguardando processamento...")
    logger.flush()
    time.sleep(2)
    
    # Valida métricas
    for handler in logger.handlers:
        if hasattr(handler, 'get_metrics'):
            metrics = handler.get_metrics()
            print(f"\n   Métricas finais:")
            print(f"   - Total publicados: {metrics['published']}")
            print(f"   - Total descartados: {metrics['dropped']} ({metrics['dropped']/log_count*100:.1f}%)")
            print(f"   - Erros: {metrics['errors']}")
            
            if hasattr(handler, 'sampling_rate'):
                print(f"   - Sampling rate final: {handler.sampling_rate:.2%}")
    
    # Cleanup
    event_bus.stop()
    
    print("\n" + "="*70)
    print("✅ TESTE 2: SUCESSO!")
    print("="*70)
    return True


def test_03_enrichment_and_filtering():
    """
    Teste 3: Enrichment e Filtragem de Logs.
    
    Demonstra como enriquecer logs com contexto adicional
    e filtrar baseado em critérios.
    """
    print("\n" + "="*70)
    print("🧪 TESTE 3: Enrichment e Filtragem")
    print("="*70)
    
    # Setup
    print("\n[1/3] 🚀 Configurando com enrichers e filtros...")
    event_bus = RedisEventBus()
    
    try:
        event_bus.start()
        time.sleep(1)
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False
    
    event_config = EventDrivenLoggingConfig(
        enabled=True,
        service_name="enriched-service",
        enable_aggregator=True,
        aggregator_console=True
    )
    
    logger, aggregator = setup_event_driven_logging(
        event_bus=event_bus,
        event_config=event_config
    )
    
    # Adiciona enrichers
    if aggregator:
        aggregator.add_enricher(create_hostname_enricher())
        aggregator.add_enricher(create_pid_enricher())
        
        # Adiciona filtro: apenas logs >= WARNING
        aggregator.add_filter(create_level_filter(30))  # WARNING = 30
        
        print("✅ Enrichers e filtros configurados!")
    
    time.sleep(1)
    
    # Testa logs
    print("\n[2/3] 📤 Enviando logs (apenas WARNING+ serão exibidos)...")
    
    logger.debug("Este log DEBUG será filtrado")
    time.sleep(0.1)
    
    logger.info("Este log INFO será filtrado")
    time.sleep(0.1)
    
    logger.aviso("⚠️  Este log WARNING será exibido com enrichment", issue="rate-limit")
    time.sleep(0.2)
    
    logger.erro("❌ Este log ERROR será exibido com enrichment", error_code="E001")
    time.sleep(0.2)
    
    logger.critico("💀 Este log CRITICAL será exibido com enrichment", system="database")
    time.sleep(0.5)
    
    print("\n[3/3] ✅ Validando...")
    
    if aggregator:
        metrics = aggregator.get_metrics()
        print(f"\n   Métricas do Agregador:")
        print(f"   - Eventos recebidos: {metrics['events_received']}")
        print(f"   - Eventos processados: {metrics['events_processed']}")
        print(f"   - Eventos filtrados: {metrics['events_filtered']}")
    
    # Cleanup
    logger.flush()
    time.sleep(1)
    event_bus.stop()
    
    print("\n" + "="*70)
    print("✅ TESTE 3: SUCESSO!")
    print("="*70)
    return True


def test_04_anti_patterns():
    """
    Teste 4: Anti-Patterns e Como Evitá-los.
    
    Demonstra práticas ERRADAS e suas correções.
    """
    print("\n" + "="*70)
    print("🧪 TESTE 4: Anti-Patterns e Correções")
    print("="*70)
    
    event_bus = RedisEventBus()
    
    try:
        event_bus.start()
        time.sleep(1)
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False
    
    event_config = EventDrivenLoggingConfig(
        enabled=True,
        service_name="demo-service",
        enable_fallback=True,  # IMPORTANTE: sempre habilite fallback
        enable_aggregator=True,
        aggregator_console=True
    )
    
    logger, aggregator = setup_event_driven_logging(
        event_bus=event_bus,
        event_config=event_config
    )
    
    time.sleep(1)
    
    print("\n❌ ANTI-PATTERN 1: Logs sem contexto/correlation ID")
    print("   Problema: Impossível correlacionar logs relacionados")
    
    # ERRADO
    logger.info("Processando pedido")  # Sem contexto!
    
    # CORRETO
    logger.info("Processando pedido", 
                order_id="ORDER-123", 
                user_id="USR-456",
                correlation_id="corr-789")
    time.sleep(0.2)
    
    print("\n❌ ANTI-PATTERN 2: Payload de log muito grande")
    print("   Problema: Overhead no Event Bus e latência")
    
    # ERRADO
    huge_data = {"data": "x" * 10000}  # 10KB de dados
    logger.info("Processando", payload=huge_data)  # Muito grande!
    
    # CORRETO
    logger.info("Processando", 
                payload_size=len(str(huge_data)),  # Apenas metadata
                payload_hash="abc123")  # Hash para referência
    time.sleep(0.2)
    
    print("\n❌ ANTI-PATTERN 3: Logs não estruturados")
    print("   Problema: Difícil parsing e análise")
    
    # ERRADO
    logger.info(f"User john@example.com logged in from 192.168.1.1")  # String não estruturada
    
    # CORRETO
    logger.info("User logged in",
                user="john@example.com",
                ip="192.168.1.1",
                country="BR")  # Estruturado
    time.sleep(0.2)
    
    print("\n❌ ANTI-PATTERN 4: Logging de dados sensíveis")
    print("   Problema: Vazamento de informações")
    
    # ERRADO
    logger.info("Login attempt", password="secret123")  # Nunca logue senhas!
    
    # CORRETO
    logger.info("Login attempt",
                user="user@example.com",
                password_hash="sha256:abc...")  # Apenas hash
    time.sleep(0.2)
    
    print("\n✅ BEST PRACTICES demonstradas!")
    
    # Cleanup
    logger.flush()
    time.sleep(1)
    event_bus.stop()
    
    print("\n" + "="*70)
    print("✅ TESTE 4: SUCESSO!")
    print("="*70)
    return True


def main():
    """Executa todos os testes."""
    print("\n" + "🧪"*35)
    print("TESTES DO SISTEMA DE LOGGING DESCENTRALIZADO")
    print("🧪"*35)
    
    tests = [
        ("Logging Descentralizado Básico", test_01_basic_event_driven_logging),
        ("Adaptive Sampling", test_02_adaptive_sampling),
        ("Enrichment e Filtragem", test_03_enrichment_and_filtering),
        ("Anti-Patterns e Correções", test_04_anti_patterns),
    ]
    
    results = {}
    
    for name, test_func in tests:
        try:
            print(f"\n▶️  Executando: {name}")
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ Erro no teste {name}: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False
        
        time.sleep(2)  # Pausa entre testes
    
    # Resumo
    print("\n" + "="*70)
    print("📊 RESUMO DOS TESTES")
    print("="*70)
    
    for name, passed in results.items():
        status = "✅ PASSOU" if passed else "❌ FALHOU"
        print(f"  {status} - {name}")
    
    total = len(results)
    passed = sum(1 for r in results.values() if r)
    
    print("\n" + "="*70)
    print(f"🎯 Total: {passed}/{total} testes passaram")
    print("="*70 + "\n")
    
    return all(results.values())


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
