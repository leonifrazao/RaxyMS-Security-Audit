"""Testes para handlers de eventos."""

import pytest
from unittest.mock import Mock, MagicMock
from raxy.core.events.handlers import (
    EventHandlerRegistry,
    create_logging_handler,
    create_rewards_handler,
    create_session_handler,
    create_account_handler,
    register_default_handlers,
)


class TestEventHandlerRegistry:
    """Testes para EventHandlerRegistry."""
    
    def test_add_handler(self):
        """Testa adição de handler."""
        registry = EventHandlerRegistry()
        
        def my_handler(data):
            pass
        
        registry.add_handler("test.event", my_handler)
        handlers = registry.get_handlers("test.event")
        
        assert len(handlers) == 1
        assert handlers[0] == my_handler
    
    def test_decorator_handler(self):
        """Testa decorator de handler."""
        registry = EventHandlerRegistry()
        
        @registry.handler("test.event")
        def my_handler(data):
            pass
        
        handlers = registry.get_handlers("test.event")
        assert len(handlers) == 1
        assert handlers[0] == my_handler
    
    def test_remove_handler(self):
        """Testa remoção de handler."""
        registry = EventHandlerRegistry()
        
        def handler1(data):
            pass
        
        def handler2(data):
            pass
        
        registry.add_handler("test.event", handler1)
        registry.add_handler("test.event", handler2)
        
        assert len(registry.get_handlers("test.event")) == 2
        
        registry.remove_handler("test.event", handler1)
        assert len(registry.get_handlers("test.event")) == 1
        
        registry.remove_handler("test.event")
        assert len(registry.get_handlers("test.event")) == 0
    
    def test_register_all(self):
        """Testa registro de todos os handlers."""
        registry = EventHandlerRegistry()
        event_bus = Mock()
        
        @registry.handler("event1")
        def handler1(data):
            pass
        
        @registry.handler("event2")
        def handler2(data):
            pass
        
        registry.register_all(event_bus)
        
        assert event_bus.subscribe.call_count == 2
    
    def test_unregister_all(self):
        """Testa desregistro de todos os handlers."""
        registry = EventHandlerRegistry()
        event_bus = Mock()
        
        @registry.handler("event1")
        def handler1(data):
            pass
        
        registry.unregister_all(event_bus)
        
        assert event_bus.unsubscribe.call_count == 1


class TestHandlerFactories:
    """Testes para factories de handlers."""
    
    def test_create_logging_handler(self):
        """Testa criação de logging handler."""
        logger = Mock()
        handler = create_logging_handler(logger)
        
        handler({"event_type": "test.event"})
        
        logger.info.assert_called_once()
    
    def test_create_rewards_handler(self):
        """Testa criação de rewards handlers."""
        logger = Mock()
        handlers = create_rewards_handler(logger)
        
        assert "rewards.points.fetched" in handlers
        assert "rewards.collected" in handlers
        assert "task.completed" in handlers
        
        # Testa handler de pontos
        handlers["rewards.points.fetched"]({"account_id": "test", "points": 100})
        assert logger.debug.called
    
    def test_create_session_handler(self):
        """Testa criação de session handlers."""
        logger = Mock()
        handlers = create_session_handler(logger)
        
        assert "session.started" in handlers
        assert "session.ended" in handlers
        assert "session.error" in handlers
        
        # Testa handler de início
        handlers["session.started"]({"account_id": "test", "proxy_id": "proxy1"})
        assert logger.debug.called
    
    def test_create_account_handler(self):
        """Testa criação de account handlers."""
        logger = Mock()
        handlers = create_account_handler(logger)
        
        assert "account.logged_in" in handlers
        assert "account.logged_out" in handlers
        
        # Testa handler de login
        handlers["account.logged_in"]({"email": "test@example.com"})
        assert logger.debug.called
    
    def test_register_default_handlers(self):
        """Testa registro de handlers padrão."""
        event_bus = Mock()
        logger = Mock()
        
        register_default_handlers(event_bus, logger)
        
        # Deve ter registrado múltiplos eventos
        assert event_bus.subscribe.call_count > 0
        
        # Verifica alguns eventos específicos
        calls = [call[0][0] for call in event_bus.subscribe.call_args_list]
        assert "rewards.points.fetched" in calls
        assert "session.started" in calls
        assert "account.logged_in" in calls


class TestHandlerExecution:
    """Testes de execução de handlers."""
    
    def test_rewards_handler_execution(self):
        """Testa execução real de handler de rewards."""
        logger = Mock()
        handlers = create_rewards_handler(logger)
        
        # Simula evento de coleta de recompensas
        handlers["rewards.collected"]({
            "account_id": "test@example.com",
            "tasks_completed": 5,
            "tasks_failed": 2,
            "total_tasks": 7
        })
        
        logger.info.assert_called_once()
        call_args = logger.info.call_args[0][0]
        assert "5/7" in call_args
    
    def test_session_handler_execution(self):
        """Testa execução real de handler de sessão."""
        logger = Mock()
        handlers = create_session_handler(logger)
        
        # Simula evento de sessão encerrada
        handlers["session.ended"]({
            "account_id": "test@example.com",
            "duration_seconds": 45.5,
            "reason": "Normal closure"
        })
        
        logger.debug.assert_called_once()
        call_args = logger.debug.call_args[0][0]
        assert "45.5" in call_args
    
    def test_error_handler_execution(self):
        """Testa execução de handler de erro."""
        logger = Mock()
        handlers = create_session_handler(logger)
        
        # Simula erro recuperável
        handlers["session.error"]({
            "account_id": "test@example.com",
            "error_type": "ConnectionError",
            "is_recoverable": True
        })
        
        logger.debug.assert_called_once()
        call_args = logger.debug.call_args[0][0]
        assert "aviso" in call_args
        
        # Simula erro não recuperável
        logger.reset_mock()
        handlers["session.error"]({
            "account_id": "test@example.com",
            "error_type": "AuthenticationError",
            "is_recoverable": False
        })
        
        logger.debug.assert_called_once()
        call_args = logger.debug.call_args[0][0]
        assert "erro" in call_args
