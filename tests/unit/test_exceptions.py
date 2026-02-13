"""Unit tests for ZTC exception classes"""

import pytest
from ztc.exceptions import (
    ZTCError,
    MissingCapabilityError,
    LockFileValidationError,
    RuntimeDependencyError
)


class TestZTCError:
    """Test base ZTCError exception class"""
    
    def test_basic_error_message(self):
        """Test error with message only"""
        error = ZTCError("Something went wrong")
        
        assert error.message == "Something went wrong"
        assert error.help_text is None
        assert str(error) == "Something went wrong"
    
    def test_error_with_help_text(self):
        """Test error with message and help text"""
        error = ZTCError(
            "Something went wrong",
            help_text="Try running 'ztc init' first"
        )
        
        assert error.message == "Something went wrong"
        assert error.help_text == "Try running 'ztc init' first"
        assert "Help: Try running 'ztc init' first" in str(error)
    
    def test_error_is_exception(self):
        """Test that ZTCError is a proper Exception"""
        error = ZTCError("test")
        assert isinstance(error, Exception)


class TestMissingCapabilityError:
    """Test MissingCapabilityError exception class"""
    
    def test_basic_missing_capability(self):
        """Test missing capability error without available adapters"""
        error = MissingCapabilityError(
            adapter_name="talos",
            capability="cloud-infrastructure"
        )
        
        assert error.adapter_name == "talos"
        assert error.capability == "cloud-infrastructure"
        assert "talos" in error.message
        assert "cloud-infrastructure" in error.message
        assert "Add an adapter" in error.help_text
    
    def test_missing_capability_with_suggestions(self):
        """Test missing capability error with available adapter suggestions"""
        error = MissingCapabilityError(
            adapter_name="talos",
            capability="cloud-infrastructure",
            available_adapters=["hetzner", "aws", "gcp"]
        )
        
        assert error.available_adapters == ["hetzner", "aws", "gcp"]
        assert "hetzner" in error.help_text
        assert "aws" in error.help_text
        assert "gcp" in error.help_text
        assert "ztc init" in error.help_text
    
    def test_missing_capability_is_ztc_error(self):
        """Test that MissingCapabilityError inherits from ZTCError"""
        error = MissingCapabilityError("test", "capability")
        assert isinstance(error, ZTCError)


class TestLockFileValidationError:
    """Test LockFileValidationError exception class"""
    
    def test_basic_validation_error(self):
        """Test lock file validation error with reason only"""
        error = LockFileValidationError("platform.yaml hash mismatch")
        
        assert error.reason == "platform.yaml hash mismatch"
        assert "platform.yaml hash mismatch" in error.message
        assert "ztc render" in error.help_text
    
    def test_validation_error_with_values(self):
        """Test lock file validation error with expected and actual values"""
        error = LockFileValidationError(
            reason="Hash mismatch",
            lock_file_path="platform/lock.json",
            expected_value="abc123",
            actual_value="def456"
        )
        
        assert error.expected_value == "abc123"
        assert error.actual_value == "def456"
        assert "abc123" in error.help_text
        assert "def456" in error.help_text
    
    def test_validation_error_remediation_hints(self):
        """Test that validation error includes remediation hints"""
        error = LockFileValidationError("test")
        
        assert "ztc render" in error.help_text
        assert "drift" in error.help_text.lower()
    
    def test_validation_error_is_ztc_error(self):
        """Test that LockFileValidationError inherits from ZTCError"""
        error = LockFileValidationError("test")
        assert isinstance(error, ZTCError)


class TestRuntimeDependencyError:
    """Test RuntimeDependencyError exception class"""
    
    def test_basic_dependency_error(self):
        """Test runtime dependency error with tool name only"""
        error = RuntimeDependencyError("jq")
        
        assert error.tool_name == "jq"
        assert "jq" in error.message
        assert "Install 'jq'" in error.help_text
    
    def test_dependency_error_with_context(self):
        """Test runtime dependency error with required_for context"""
        error = RuntimeDependencyError(
            tool_name="kubectl",
            required_for="bootstrap execution"
        )
        
        assert error.required_for == "bootstrap execution"
        assert "bootstrap execution" in error.message
    
    def test_dependency_error_with_custom_instructions(self):
        """Test runtime dependency error with custom install instructions"""
        error = RuntimeDependencyError(
            tool_name="custom-tool",
            install_instructions="Download from https://example.com"
        )
        
        assert "Download from https://example.com" in error.help_text
    
    def test_dependency_error_default_hints(self):
        """Test that common tools have default installation hints"""
        # Test jq
        jq_error = RuntimeDependencyError("jq")
        assert "brew install jq" in jq_error.help_text
        
        # Test yq
        yq_error = RuntimeDependencyError("yq")
        assert "brew install yq" in yq_error.help_text
        
        # Test kubectl
        kubectl_error = RuntimeDependencyError("kubectl")
        assert "kubernetes.io" in kubectl_error.help_text
        
        # Test talosctl
        talosctl_error = RuntimeDependencyError("talosctl")
        assert "talos.dev" in talosctl_error.help_text
    
    def test_dependency_error_is_ztc_error(self):
        """Test that RuntimeDependencyError inherits from ZTCError"""
        error = RuntimeDependencyError("test")
        assert isinstance(error, ZTCError)


class TestErrorFormatting:
    """Test error message formatting"""
    
    def test_error_string_representation(self):
        """Test that errors format correctly as strings"""
        error = ZTCError(
            "Test error",
            help_text="Test help"
        )
        
        error_str = str(error)
        assert "Test error" in error_str
        assert "Help: Test help" in error_str
    
    def test_error_without_help_text_formatting(self):
        """Test that errors without help text format correctly"""
        error = ZTCError("Test error")
        
        error_str = str(error)
        assert error_str == "Test error"
        assert "Help:" not in error_str
