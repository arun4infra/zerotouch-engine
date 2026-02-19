"""Integration test for adapter read-only restrictions during traversal

Validates Requirement 9.10: Adapters SHALL be restricted to read-only operations
during workflow traversal, state-mutating operations are prohibited until completion phase.
"""

import pytest
from workflow_engine.adapters.base import PlatformAdapter, InputPrompt, AdapterOutput
from workflow_engine.adapters.operation_mode import (
    OperationType, OperationMode, OperationModeContext,
    ReadOnlyViolationError, traversal_mode, completion_mode, enforce_read_only
)
from typing import List, Dict, Any, Type
from pydantic import BaseModel


class MockAdapterConfig(BaseModel):
    """Mock config for test adapter"""
    test_field: str = "test"


class MockAdapter(PlatformAdapter):
    """Mock adapter for testing read-only restrictions"""
    
    def __init__(self, config: Dict[str, Any], jinja_env=None):
        """Override init to avoid loading adapter.yaml"""
        self.config = config
        self.name = "mock_adapter"
        self.phase = "test"
        self._jinja_env = jinja_env
        self._platform_metadata = {}
        self._all_adapters_config = {}
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return MockAdapterConfig
    
    def get_required_inputs(self) -> List[InputPrompt]:
        return [
            InputPrompt(
                name="test_input",
                prompt="Test input",
                type="string"
            )
        ]
    
    def init(self) -> List:
        return []
    
    def pre_work_scripts(self) -> List:
        return []
    
    def bootstrap_scripts(self) -> List:
        return []
    
    def post_work_scripts(self) -> List:
        return []
    
    def validation_scripts(self) -> List:
        return []
    
    async def render(self, ctx) -> AdapterOutput:
        # Enforce read-only restriction
        enforce_read_only(OperationType.MUTATE)
        
        return AdapterOutput(
            manifests={},
            stages=[],
            env_vars={},
            capabilities={},
            data={}
        )


class TestOperationModeContext:
    """Test operation mode context management"""
    
    def test_initial_state_is_none(self):
        """Operation mode should be None initially"""
        OperationModeContext.clear()
        assert OperationModeContext.get_mode() is None
        assert not OperationModeContext.is_traversal_mode()
        assert not OperationModeContext.is_completion_mode()
    
    def test_set_traversal_mode(self):
        """Should set and detect traversal mode"""
        OperationModeContext.clear()
        OperationModeContext.set_mode(OperationMode.TRAVERSAL)
        assert OperationModeContext.is_traversal_mode()
        assert not OperationModeContext.is_completion_mode()
        OperationModeContext.clear()
    
    def test_set_completion_mode(self):
        """Should set and detect completion mode"""
        OperationModeContext.clear()
        OperationModeContext.set_mode(OperationMode.COMPLETION)
        assert OperationModeContext.is_completion_mode()
        assert not OperationModeContext.is_traversal_mode()
        OperationModeContext.clear()


class TestTraversalModeContextManager:
    """Test traversal mode context manager"""
    
    def test_enters_and_exits_traversal_mode(self):
        """Context manager should enter and exit traversal mode"""
        OperationModeContext.clear()
        assert OperationModeContext.get_mode() is None
        
        with traversal_mode():
            assert OperationModeContext.is_traversal_mode()
        
        assert OperationModeContext.get_mode() is None
    
    def test_restores_previous_mode(self):
        """Context manager should restore previous mode"""
        OperationModeContext.clear()
        OperationModeContext.set_mode(OperationMode.COMPLETION)
        
        with traversal_mode():
            assert OperationModeContext.is_traversal_mode()
        
        assert OperationModeContext.is_completion_mode()
        OperationModeContext.clear()


class TestCompletionModeContextManager:
    """Test completion mode context manager"""
    
    def test_enters_and_exits_completion_mode(self):
        """Context manager should enter and exit completion mode"""
        OperationModeContext.clear()
        assert OperationModeContext.get_mode() is None
        
        with completion_mode():
            assert OperationModeContext.is_completion_mode()
        
        assert OperationModeContext.get_mode() is None
    
    def test_restores_previous_mode(self):
        """Context manager should restore previous mode"""
        OperationModeContext.clear()
        OperationModeContext.set_mode(OperationMode.TRAVERSAL)
        
        with completion_mode():
            assert OperationModeContext.is_completion_mode()
        
        assert OperationModeContext.is_traversal_mode()
        OperationModeContext.clear()


class TestReadOnlyEnforcement:
    """Test read-only enforcement during traversal"""
    
    def test_read_operations_allowed_in_traversal_mode(self):
        """Read operations should be allowed during traversal"""
        OperationModeContext.clear()
        with traversal_mode():
            # Should not raise
            enforce_read_only(OperationType.READ)
        OperationModeContext.clear()
    
    def test_mutate_operations_blocked_in_traversal_mode(self):
        """Mutate operations should be blocked during traversal"""
        OperationModeContext.clear()
        with traversal_mode():
            with pytest.raises(ReadOnlyViolationError) as exc_info:
                enforce_read_only(OperationType.MUTATE)
            
            assert "State-mutating operations are prohibited" in str(exc_info.value)
            assert "workflow traversal" in str(exc_info.value)
        OperationModeContext.clear()
    
    def test_mutate_operations_allowed_in_completion_mode(self):
        """Mutate operations should be allowed during completion"""
        OperationModeContext.clear()
        with completion_mode():
            # Should not raise
            enforce_read_only(OperationType.MUTATE)
        OperationModeContext.clear()
    
    def test_mutate_operations_allowed_without_mode(self):
        """Mutate operations should be allowed when no mode is set"""
        OperationModeContext.clear()
        # Should not raise
        enforce_read_only(OperationType.MUTATE)


class TestAdapterReadOnlyRestrictions:
    """Test adapter methods respect read-only restrictions"""
    
    @pytest.mark.asyncio
    async def test_get_required_inputs_allowed_in_traversal(self):
        """get_required_inputs should work during traversal (read operation)"""
        OperationModeContext.clear()
        adapter = MockAdapter(config={}, jinja_env=None)
        
        with traversal_mode():
            inputs = adapter.get_required_inputs()
            assert len(inputs) == 1
            assert inputs[0].name == "test_input"
        
        OperationModeContext.clear()
    
    @pytest.mark.asyncio
    async def test_render_blocked_in_traversal(self):
        """render should be blocked during traversal (mutate operation)"""
        OperationModeContext.clear()
        adapter = MockAdapter(config={}, jinja_env=None)
        
        with traversal_mode():
            with pytest.raises(ReadOnlyViolationError):
                await adapter.render(None)
        
        OperationModeContext.clear()
    
    @pytest.mark.asyncio
    async def test_render_allowed_in_completion(self):
        """render should be allowed during completion phase"""
        OperationModeContext.clear()
        adapter = MockAdapter(config={}, jinja_env=None)
        
        with completion_mode():
            result = await adapter.render(None)
            assert isinstance(result, AdapterOutput)
        
        OperationModeContext.clear()
    
    @pytest.mark.asyncio
    async def test_get_dynamic_choices_allowed_in_traversal(self):
        """get_dynamic_choices should work during traversal (read operation)"""
        OperationModeContext.clear()
        adapter = MockAdapter(config={}, jinja_env=None)
        input_prompt = InputPrompt(
            name="test",
            prompt="Test",
            type="choice",
            choices=["a", "b"]
        )
        
        with traversal_mode():
            choices = await adapter.get_dynamic_choices(input_prompt, {})
            assert choices == ["a", "b"]
        
        OperationModeContext.clear()
