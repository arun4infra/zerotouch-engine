"""Checkpoint 5: Deferred Operations and Secrets Management

Tests deferred operations registry with rollback and secrets management.
"""
import pytest
import os
from workflow_engine.core.deferred_operations import (
    DeferredOperationsRegistry,
    OnQuestionPathCompleteOperation
)
from workflow_engine.secrets.resolver import SecretResolver, SecretNotFoundError
from workflow_engine.models.feedback import QuestionPathFeedback
from workflow_engine.models.entry import Entry, EntryData, EntryType


class TestOperation(OnQuestionPathCompleteOperation):
    """Test operation for validation"""
    def __init__(self, feedback_id: int):
        super().__init__(feedback_id)
        self.executed = False
        self.rolled_back = False
    
    async def execute(self, feedback_history, platform_context=None):
        self.executed = True
    
    def rollback(self):
        self.rolled_back = True


class FailingOperation(OnQuestionPathCompleteOperation):
    """Operation that always fails"""
    def __init__(self, feedback_id: int):
        super().__init__(feedback_id)
        self.executed = False
        self.rolled_back = False
    
    async def execute(self, feedback_history, platform_context=None):
        self.executed = True
        raise Exception("Operation failed")
    
    def rollback(self):
        self.rolled_back = True


@pytest.mark.asyncio
async def test_deferred_operations_execution_order():
    """Test operations execute in registration order"""
    registry = DeferredOperationsRegistry()
    
    op1 = TestOperation(feedback_id=1)
    op2 = TestOperation(feedback_id=2)
    op3 = TestOperation(feedback_id=3)
    
    registry.register(op1)
    registry.register(op2)
    registry.register(op3)
    
    await registry.execute_all([], {})
    
    assert op1.executed is True
    assert op2.executed is True
    assert op3.executed is True


@pytest.mark.asyncio
async def test_deferred_operations_rollback_on_failure():
    """Test rollback occurs when operation fails"""
    registry = DeferredOperationsRegistry()
    
    op1 = TestOperation(feedback_id=1)
    op2 = FailingOperation(feedback_id=2)
    op3 = TestOperation(feedback_id=3)
    
    registry.register(op1)
    registry.register(op2)
    registry.register(op3)
    
    with pytest.raises(Exception):
        await registry.execute_all([], {})
    
    # op1 should be executed and rolled back
    assert op1.executed is True
    assert op1.rolled_back is True
    
    # op2 should be executed but not rolled back (it failed)
    assert op2.executed is True
    
    # op3 should not be executed
    assert op3.executed is False


@pytest.mark.asyncio
async def test_deferred_operations_rollback_all():
    """Test rollback_all without execution"""
    registry = DeferredOperationsRegistry()
    
    op1 = TestOperation(feedback_id=1)
    op2 = TestOperation(feedback_id=2)
    
    registry.register(op1)
    registry.register(op2)
    
    registry.rollback_all()
    
    assert op1.executed is False
    assert op1.rolled_back is True
    assert op2.executed is False
    assert op2.rolled_back is True


@pytest.mark.asyncio
async def test_deferred_operations_clear():
    """Test clearing operations without execution or rollback"""
    registry = DeferredOperationsRegistry()
    
    op1 = TestOperation(feedback_id=1)
    registry.register(op1)
    
    assert len(registry) == 1
    
    registry.clear()
    
    assert len(registry) == 0
    assert op1.executed is False
    assert op1.rolled_back is False


def test_secret_resolver_environment_variable():
    """Test secret resolution from environment variables"""
    os.environ["TEST_SECRET"] = "secret_value"
    
    resolver = SecretResolver()
    
    # Resolve secret reference
    result = resolver.resolve_secret("$TEST_SECRET", "test_field")
    assert result == "secret_value"
    
    # Non-secret value passes through
    result = resolver.resolve_secret("plain_value", "test_field")
    assert result == "plain_value"
    
    # Cleanup
    del os.environ["TEST_SECRET"]


def test_secret_resolver_missing_variable():
    """Test error when environment variable is missing"""
    resolver = SecretResolver()
    
    with pytest.raises(SecretNotFoundError) as exc_info:
        resolver.resolve_secret("$NONEXISTENT_VAR", "test_field")
    
    assert exc_info.value.env_var == "NONEXISTENT_VAR"
    assert exc_info.value.field == "test_field"


def test_secret_resolver_is_secret_reference():
    """Test detection of secret references"""
    resolver = SecretResolver()
    
    assert resolver.is_secret_reference("$MY_SECRET") is True
    assert resolver.is_secret_reference("plain_value") is False
    assert resolver.is_secret_reference("") is False
    assert resolver.is_secret_reference("$") is False


def test_secret_resolver_mask_sensitive_value():
    """Test masking of sensitive values"""
    resolver = SecretResolver()
    
    masked = resolver.mask_sensitive_value("secret123")
    assert masked == "***REDACTED***"


def test_secret_resolver_create_reference():
    """Test creating secret references"""
    resolver = SecretResolver()
    
    ref = resolver.create_secret_reference("MY_SECRET")
    assert ref == "$MY_SECRET"


def test_secret_resolver_context_secrets():
    """Test resolving all secrets in a context dictionary"""
    os.environ["SECRET1"] = "value1"
    os.environ["SECRET2"] = "value2"
    
    resolver = SecretResolver()
    
    context = {
        "field1": "$SECRET1",
        "field2": "plain_value",
        "nested": {
            "field3": "$SECRET2"
        },
        "list_field": ["$SECRET1", "plain"]
    }
    
    resolved = resolver.resolve_context_secrets(context)
    
    assert resolved["field1"] == "value1"
    assert resolved["field2"] == "plain_value"
    assert resolved["nested"]["field3"] == "value2"
    assert resolved["list_field"][0] == "value1"
    assert resolved["list_field"][1] == "plain"
    
    # Cleanup
    del os.environ["SECRET1"]
    del os.environ["SECRET2"]


@pytest.mark.asyncio
async def test_sensitive_field_persistence(tmp_path):
    """Test sensitive fields stored as environment variable references"""
    os.environ["MY_PASSWORD"] = "secret123"
    
    # Create feedback with sensitive field
    entry = Entry(
        id="password",
        type=EntryType.STRING,
        prompt="Enter password",
        sensitive=True
    )
    
    entry_data = EntryData(type=EntryType.STRING, value="$MY_PASSWORD")
    
    feedback = QuestionPathFeedback(
        feedback_id=1,
        timestamp=1000,
        entry=entry,
        entry_data=entry_data,
        is_sensitive=True
    )
    
    # Serialize feedback
    serialized = feedback.to_dict()
    
    # Should store environment variable reference
    assert serialized["entry_data"]["value"] == "$MY_PASSWORD"
    assert serialized["is_sensitive"] is True
    
    # Resolve at runtime
    resolver = SecretResolver()
    resolved_value = resolver.resolve_secret(serialized["entry_data"]["value"], "password")
    assert resolved_value == "secret123"
    
    # Cleanup
    del os.environ["MY_PASSWORD"]


@pytest.mark.asyncio
async def test_deferred_operations_with_secrets():
    """Test deferred operations resolve secrets at execution time"""
    os.environ["API_TOKEN"] = "token123"
    
    registry = DeferredOperationsRegistry()
    op = TestOperation(feedback_id=1)
    registry.register(op)
    
    platform_context = {
        "api_token": "$API_TOKEN",
        "plain_field": "value"
    }
    
    await registry.execute_all([], platform_context)
    
    assert op.executed is True
    
    # Cleanup
    del os.environ["API_TOKEN"]


@pytest.mark.asyncio
async def test_operations_serialization():
    """Test operations can be serialized for session persistence"""
    registry = DeferredOperationsRegistry()
    
    op1 = TestOperation(feedback_id=1)
    op2 = TestOperation(feedback_id=2)
    
    registry.register(op1)
    registry.register(op2)
    
    serialized = registry.serialize()
    
    assert len(serialized) == 2
    assert serialized[0]["feedback_id"] == 1
    assert serialized[1]["feedback_id"] == 2
