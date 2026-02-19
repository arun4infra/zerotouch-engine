"""Checkpoint 6: Adapter Integration

Tests adapter loading, InputPrompt translation, PlatformContext construction,
cross-adapter dependencies, and dynamic choice resolution.
"""
import pytest
from pathlib import Path
from workflow_engine.adapters.registry import AdapterRegistry
from workflow_engine.adapters.translator import AdapterQuestionTranslator
from workflow_engine.adapters.generator import AdapterWorkflowGenerator
from workflow_engine.adapters.base import InputPrompt, PlatformAdapter
from workflow_engine.models.workflow_dsl import QuestionNode, ValidationRules
from pydantic import BaseModel
from typing import List, Dict, Any


class TestAdapterConfig(BaseModel):
    """Test adapter configuration"""
    field1: str
    field2: int


class TestAdapter(PlatformAdapter):
    """Test adapter for integration tests"""
    
    @property
    def config_model(self):
        return TestAdapterConfig
    
    def load_metadata(self) -> Dict[str, Any]:
        """Override to provide test metadata without adapter.yaml"""
        return {
            "name": "test",
            "phase": "foundation",
            "selection_group": "test_group"
        }
    
    def get_required_inputs(self) -> List[InputPrompt]:
        return [
            InputPrompt(
                name="field1",
                prompt="Enter field 1",
                type="string",
                validation=r"^[a-z]+$"
            ),
            InputPrompt(
                name="field2",
                prompt="Enter field 2",
                type="integer"
            )
        ]
    
    def init(self):
        return []
    
    def pre_work_scripts(self):
        return []
    
    def bootstrap_scripts(self):
        return []
    
    def post_work_scripts(self):
        return []
    
    def validation_scripts(self):
        return []
    
    async def render(self, ctx):
        return None


def test_adapter_registry_registration():
    """Test adapter registration and retrieval"""
    registry = AdapterRegistry(auto_discover=False)
    
    # Register test adapter
    registry.register(TestAdapter)
    
    # Retrieve adapter class
    adapter_class = registry.get_adapter_class("test")
    assert adapter_class == TestAdapter
    
    # List adapters
    adapters = registry.list_adapters()
    assert "test" in adapters


def test_adapter_registry_get_adapter():
    """Test adapter instantiation with config"""
    registry = AdapterRegistry(auto_discover=False)
    registry.register(TestAdapter)
    
    config = {"field1": "value", "field2": 42}
    adapter = registry.get_adapter("test", config)
    
    assert isinstance(adapter, TestAdapter)
    assert adapter.config == config


def test_adapter_registry_error_handling():
    """Test adapter registry error handling"""
    registry = AdapterRegistry(auto_discover=False)
    
    # Non-existent adapter
    with pytest.raises(KeyError):
        registry.get_adapter_class("nonexistent")
    
    # Non-existent adapter instantiation
    with pytest.raises(KeyError):
        registry.get_adapter("nonexistent", {})


def test_input_prompt_translation():
    """Test InputPrompt to QuestionNode translation"""
    translator = AdapterQuestionTranslator()
    
    prompt = InputPrompt(
        name="api_token",
        prompt="Enter API token",
        type="password",
        help_text="Your API token",
        default="default_value",
        validation=r"^[A-Za-z0-9]+$"
    )
    
    question = translator.translate_input_prompt(prompt, "test_adapter")
    
    assert question.id == "test_adapter.api_token"
    assert question.type == "string"  # password maps to string
    assert question.prompt == "Enter API token"
    assert question.help_text == "Your API token"
    assert question.default == "default_value"
    assert question.sensitive is True  # password type sets sensitive flag
    assert question.validation.regex == r"^[A-Za-z0-9]+$"


def test_input_prompt_type_mapping():
    """Test type mapping from InputPrompt to workflow DSL"""
    translator = AdapterQuestionTranslator()
    
    # String type
    prompt = InputPrompt(name="field", prompt="Test", type="string")
    question = translator.translate_input_prompt(prompt, "adapter")
    assert question.type == "string"
    
    # Password type (maps to string with sensitive flag)
    prompt = InputPrompt(name="field", prompt="Test", type="password")
    question = translator.translate_input_prompt(prompt, "adapter")
    assert question.type == "string"
    assert question.sensitive is True
    
    # Choice type
    prompt = InputPrompt(name="field", prompt="Test", type="choice", choices=["a", "b"])
    question = translator.translate_input_prompt(prompt, "adapter")
    assert question.type == "choice"
    assert question.validation.choices == ["a", "b"]
    
    # Integer type
    prompt = InputPrompt(name="field", prompt="Test", type="integer")
    question = translator.translate_input_prompt(prompt, "adapter")
    assert question.type == "integer"
    
    # Boolean type
    prompt = InputPrompt(name="field", prompt="Test", type="boolean")
    question = translator.translate_input_prompt(prompt, "adapter")
    assert question.type == "boolean"


@pytest.mark.asyncio
async def test_workflow_generation_from_adapters():
    """Test dynamic workflow generation from adapter metadata"""
    registry = AdapterRegistry(auto_discover=False)
    registry.register(TestAdapter)
    
    generator = AdapterWorkflowGenerator(registry)
    
    workflow = await generator.generate_workflow_from_adapters(["test"])
    
    assert workflow.workflow_id == "adapters_test"
    assert len(workflow.states) == 2
    assert "test.field1" in workflow.states
    assert "test.field2" in workflow.states


def test_platform_context_construction():
    """Test PlatformContext construction from session answers"""
    registry = AdapterRegistry(auto_discover=False)
    generator = AdapterWorkflowGenerator(registry)
    
    session_answers = {
        "adapter1.field1": "value1",
        "adapter1.field2": 42,
        "adapter2.field1": "value2"
    }
    
    context = generator.construct_platform_context(
        session_answers,
        ["adapter1", "adapter2"]
    )
    
    assert context["adapter1"]["field1"] == "value1"
    assert context["adapter1"]["field2"] == 42
    assert context["adapter2"]["field1"] == "value2"


def test_cross_adapter_answer_accessibility():
    """Test answers from multiple adapters are accessible"""
    translator = AdapterQuestionTranslator()
    
    adapter_answers = {
        "adapter1": {"field1": "value1", "field2": 42},
        "adapter2": {"field1": "value2", "field2": 99}
    }
    
    merged = translator.merge_adapter_answers(adapter_answers)
    
    # All adapter answers should be accessible
    assert merged["adapter1"]["field1"] == "value1"
    assert merged["adapter1"]["field2"] == 42
    assert merged["adapter2"]["field1"] == "value2"
    assert merged["adapter2"]["field2"] == 99


def test_adapter_failure_state_preservation():
    """Test adapter execution failures preserve state"""
    registry = AdapterRegistry(auto_discover=False)
    registry.register(TestAdapter)
    
    generator = AdapterWorkflowGenerator(registry)
    
    # Non-existent adapter should fail
    success, error, result = generator.execute_adapter_with_error_preservation(
        "nonexistent",
        {},
        {}
    )
    
    assert success is False
    assert error is not None
    assert result is None


def test_adapter_success_execution():
    """Test successful adapter execution"""
    registry = AdapterRegistry(auto_discover=False)
    registry.register(TestAdapter)
    
    generator = AdapterWorkflowGenerator(registry)
    
    # Valid config should succeed
    success, error, result = generator.execute_adapter_with_error_preservation(
        "test",
        {"field1": "value", "field2": 42},
        {}
    )
    
    assert success is True
    assert error is None
    assert result is not None


@pytest.mark.asyncio
async def test_dynamic_choice_resolution():
    """Test dynamic choice resolution from adapters"""
    
    class DynamicChoiceAdapter(PlatformAdapter):
        @property
        def config_model(self):
            return TestAdapterConfig
        
        def load_metadata(self) -> Dict[str, Any]:
            """Override to provide test metadata"""
            return {
                "name": "dynamic_choice_adapter",
                "phase": "foundation",
                "selection_group": "test_group"
            }
        
        def get_required_inputs(self):
            return [
                InputPrompt(
                    name="region",
                    prompt="Select region",
                    type="choice",
                    choices=["us-east", "us-west", "eu-central"]
                )
            ]
        
        async def get_dynamic_choices(self, input_prompt, context):
            """Return dynamic choices based on context"""
            if input_prompt.name == "region":
                return ["us-east-1", "us-west-2", "eu-central-1"]
            return input_prompt.choices or []
        
        def init(self):
            return []
        
        def pre_work_scripts(self):
            return []
        
        def bootstrap_scripts(self):
            return []
        
        def post_work_scripts(self):
            return []
        
        def validation_scripts(self):
            return []
        
        async def render(self, ctx):
            return None
    
    adapter = DynamicChoiceAdapter({})
    prompt = InputPrompt(
        name="region",
        prompt="Select region",
        type="choice"
    )
    
    choices = await adapter.get_dynamic_choices(prompt, {})
    
    assert len(choices) == 3
    assert "us-east-1" in choices


def test_validation_rules_translation():
    """Test validation rules translation from InputPrompt"""
    translator = AdapterQuestionTranslator()
    
    # Regex validation
    prompt = InputPrompt(
        name="field",
        prompt="Test",
        type="string",
        validation=r"^[a-z]+$"
    )
    question = translator.translate_input_prompt(prompt, "adapter")
    assert question.validation.regex == r"^[a-z]+$"
    
    # Choice validation
    prompt = InputPrompt(
        name="field",
        prompt="Test",
        type="choice",
        choices=["a", "b", "c"]
    )
    question = translator.translate_input_prompt(prompt, "adapter")
    assert question.validation.choices == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_multiple_adapters_workflow():
    """Test workflow generation from multiple adapters"""
    registry = AdapterRegistry(auto_discover=False)
    
    class Adapter1(TestAdapter):
        def load_metadata(self) -> Dict[str, Any]:
            return {
                "name": "adapter1",
                "phase": "foundation",
                "selection_group": "test_group"
            }
        
        def get_required_inputs(self):
            return [
                InputPrompt(name="a1_field1", prompt="A1 Field 1", type="string")
            ]
    
    class Adapter2(TestAdapter):
        def load_metadata(self) -> Dict[str, Any]:
            return {
                "name": "adapter2",
                "phase": "foundation",
                "selection_group": "test_group"
            }
        
        def get_required_inputs(self):
            return [
                InputPrompt(name="a2_field1", prompt="A2 Field 1", type="string")
            ]
    
    registry.register(Adapter1)
    registry.register(Adapter2)
    
    generator = AdapterWorkflowGenerator(registry)
    workflow = await generator.generate_workflow_from_adapters(["adapter1", "adapter2"])
    
    assert "adapter1.a1_field1" in workflow.states
    assert "adapter2.a2_field1" in workflow.states
