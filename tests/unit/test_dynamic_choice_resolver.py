"""Unit tests for DynamicChoiceResolver"""

import pytest
from libs.workflow_engine.adapters.dynamic_choices import DynamicChoiceResolver
from libs.workflow_engine.adapters.base import InputPrompt, PlatformAdapter
from typing import List, Dict, Any, Type
from pydantic import BaseModel


class MockAdapter(PlatformAdapter):
    """Mock adapter for testing"""
    
    def __init__(self, config: Dict[str, Any], adapter_name: str = "mock_adapter"):
        self.config = config
        self.name = adapter_name
        self.phase = "test"
        self._jinja_env = None
        self._platform_metadata = {}
        self._all_adapters_config = {}
    
    def load_metadata(self) -> Dict[str, Any]:
        return {"name": self.name, "phase": self.phase}
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return BaseModel
    
    def get_required_inputs(self) -> List[InputPrompt]:
        return []
    
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
    
    async def render(self, ctx) -> Any:
        return None


class DynamicInputPrompt(InputPrompt):
    """InputPrompt with dynamic choices method"""
    
    async def get_dynamic_choices(self, context: Dict[str, Any]) -> List[str]:
        """Fetch choices dynamically based on context"""
        return ["dynamic-choice-1", "dynamic-choice-2", "dynamic-choice-3"]


@pytest.mark.asyncio
async def test_resolve_static_choices():
    """Test resolving static choices when no dynamic method exists"""
    resolver = DynamicChoiceResolver()
    adapter = MockAdapter({})
    
    prompt = InputPrompt(
        name="test_field",
        prompt="Select option",
        type="choice",
        choices=["static-1", "static-2"]
    )
    
    choices = await resolver.resolve_choices(adapter, prompt, {})
    
    assert choices == ["static-1", "static-2"]


@pytest.mark.asyncio
async def test_resolve_dynamic_choices():
    """Test resolving dynamic choices via get_dynamic_choices method"""
    resolver = DynamicChoiceResolver()
    adapter = MockAdapter({})
    
    prompt = DynamicInputPrompt(
        name="test_field",
        prompt="Select option",
        type="choice"
    )
    
    context = {"region": "us-east-1"}
    choices = await resolver.resolve_choices(adapter, prompt, context)
    
    assert choices == ["dynamic-choice-1", "dynamic-choice-2", "dynamic-choice-3"]


@pytest.mark.asyncio
async def test_caching_dynamic_choices():
    """Test that dynamic choices are cached to avoid redundant API calls"""
    resolver = DynamicChoiceResolver()
    adapter = MockAdapter({})
    
    call_count = 0
    
    class CountingDynamicPrompt(InputPrompt):
        async def get_dynamic_choices(self, context: Dict[str, Any]) -> List[str]:
            nonlocal call_count
            call_count += 1
            return ["choice-1", "choice-2"]
    
    prompt = CountingDynamicPrompt(
        name="test_field",
        prompt="Select option",
        type="choice"
    )
    
    context = {"region": "us-east-1"}
    
    # First call should fetch
    choices1 = await resolver.resolve_choices(adapter, prompt, context)
    assert call_count == 1
    
    # Second call should use cache
    choices2 = await resolver.resolve_choices(adapter, prompt, context)
    assert call_count == 1  # No additional call
    assert choices1 == choices2


@pytest.mark.asyncio
async def test_cache_invalidation_by_adapter():
    """Test cache invalidation for specific adapter"""
    resolver = DynamicChoiceResolver()
    adapter1 = MockAdapter({}, "adapter1")
    adapter2 = MockAdapter({}, "adapter2")
    
    prompt = DynamicInputPrompt(
        name="test_field",
        prompt="Select option",
        type="choice"
    )
    
    # Populate cache for both adapters
    await resolver.resolve_choices(adapter1, prompt, {})
    await resolver.resolve_choices(adapter2, prompt, {})
    
    # Invalidate adapter1 cache
    resolver.invalidate_cache_for_adapter("adapter1")
    
    # adapter1 cache should be cleared, adapter2 should remain
    assert not any(key.startswith("adapter1:") for key in resolver._cache.keys())
    assert any(key.startswith("adapter2:") for key in resolver._cache.keys())


@pytest.mark.asyncio
async def test_clear_all_cache():
    """Test clearing all cached choices"""
    resolver = DynamicChoiceResolver()
    adapter = MockAdapter({})
    
    prompt = DynamicInputPrompt(
        name="test_field",
        prompt="Select option",
        type="choice"
    )
    
    # Populate cache
    await resolver.resolve_choices(adapter, prompt, {})
    assert len(resolver._cache) > 0
    
    # Clear cache
    resolver.clear_cache()
    assert len(resolver._cache) == 0


@pytest.mark.asyncio
async def test_fallback_on_dynamic_failure():
    """Test fallback to static choices when dynamic resolution fails"""
    resolver = DynamicChoiceResolver()
    adapter = MockAdapter({})
    
    class FailingDynamicPrompt(InputPrompt):
        async def get_dynamic_choices(self, context: Dict[str, Any]) -> List[str]:
            raise Exception("API call failed")
    
    prompt = FailingDynamicPrompt(
        name="test_field",
        prompt="Select option",
        type="choice",
        choices=["fallback-1", "fallback-2"]
    )
    
    choices = await resolver.resolve_choices(adapter, prompt, {})
    
    # Should fall back to static choices
    assert choices == ["fallback-1", "fallback-2"]


@pytest.mark.asyncio
async def test_empty_choices_when_no_static_or_dynamic():
    """Test empty list returned when no choices available"""
    resolver = DynamicChoiceResolver()
    adapter = MockAdapter({})
    
    prompt = InputPrompt(
        name="test_field",
        prompt="Select option",
        type="choice"
    )
    
    choices = await resolver.resolve_choices(adapter, prompt, {})
    
    assert choices == []
