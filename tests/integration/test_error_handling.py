"""Integration tests for error handling and user messaging"""

import pytest
from typer.testing import CliRunner
from pathlib import Path
from ztc.cli import app
from ztc.exceptions import (
    ZTCError,
    MissingCapabilityError,
    LockFileValidationError,
    RuntimeDependencyError
)

runner = CliRunner()


class TestCLIErrorHandling:
    """Test CLI error handling with Rich formatting"""
    
    def test_render_without_platform_yaml(self, tmp_path, monkeypatch):
        """Test render command fails gracefully when platform.yaml is missing"""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["render"])
        
        assert result.exit_code == 1
        assert "platform.yaml not found" in result.stdout
        assert "ztc init" in result.stdout
    
    def test_validate_without_lock_file(self, tmp_path, monkeypatch):
        """Test validate command fails gracefully when lock file is missing"""
        monkeypatch.chdir(tmp_path)
        
        # Create platform.yaml but no lock file
        platform_yaml = tmp_path / "platform.yaml"
        platform_yaml.write_text("adapters: {}")
        
        result = runner.invoke(app, ["validate"])
        
        assert result.exit_code == 1
    
    def test_version_command_displays_info(self):
        """Test version command displays CLI and adapter versions"""
        result = runner.invoke(app, ["version"])
        
        assert result.exit_code == 0
        assert "ZTC Version Information" in result.stdout
        assert "CLI Version" in result.stdout


class TestErrorMessageFormatting:
    """Test error message formatting with Rich"""
    
    def test_ztc_error_formatting(self):
        """Test that ZTC errors format with help text"""
        error = ZTCError(
            "Test error message",
            help_text="Run 'ztc init' to fix this"
        )
        
        error_str = str(error)
        assert "Test error message" in error_str
        assert "Help: Run 'ztc init' to fix this" in error_str
    
    def test_missing_capability_error_formatting(self):
        """Test that missing capability errors include suggestions"""
        error = MissingCapabilityError(
            adapter_name="talos",
            capability="cloud-infrastructure",
            available_adapters=["hetzner", "aws"]
        )
        
        error_str = str(error)
        assert "talos" in error_str
        assert "cloud-infrastructure" in error_str
        assert "hetzner" in error_str
        assert "aws" in error_str
    
    def test_lock_file_validation_error_formatting(self):
        """Test that lock file validation errors include remediation"""
        error = LockFileValidationError(
            reason="Hash mismatch",
            expected_value="abc123",
            actual_value="def456"
        )
        
        error_str = str(error)
        assert "Hash mismatch" in error_str
        assert "abc123" in error_str
        assert "def456" in error_str
        assert "ztc render" in error_str
    
    def test_runtime_dependency_error_formatting(self):
        """Test that runtime dependency errors include install instructions"""
        error = RuntimeDependencyError(
            tool_name="jq",
            required_for="bootstrap execution"
        )
        
        error_str = str(error)
        assert "jq" in error_str
        assert "bootstrap execution" in error_str
        assert "brew install jq" in error_str


class TestProgressIndicators:
    """Test progress indicators for long operations"""
    
    def test_render_shows_progress(self, tmp_path, monkeypatch):
        """Test that render command shows progress indicators"""
        monkeypatch.chdir(tmp_path)
        
        # Create minimal platform.yaml
        platform_yaml = tmp_path / "platform.yaml"
        platform_yaml.write_text("""
adapters:
  hetzner:
    version: v1.0.0
    api_token: test_token
    server_ips:
      - 192.168.1.1
""")
        
        result = runner.invoke(app, ["render"])
        
        # Should show rendering message
        assert "Rendering platform artifacts" in result.stdout


class TestHelpText:
    """Test help text and user guidance"""
    
    def test_render_help_text(self):
        """Test render command help text"""
        result = runner.invoke(app, ["render", "--help"])
        
        assert result.exit_code == 0
        assert "Generate platform artifacts" in result.stdout
        assert "--debug" in result.stdout
        assert "--partial" in result.stdout
    
    def test_bootstrap_help_text(self):
        """Test bootstrap command help text"""
        result = runner.invoke(app, ["bootstrap", "--help"])
        
        assert result.exit_code == 0
        assert "Execute bootstrap pipeline" in result.stdout
        assert "--env" in result.stdout
        assert "--skip-cache" in result.stdout
    
    def test_validate_help_text(self):
        """Test validate command help text"""
        result = runner.invoke(app, ["validate", "--help"])
        
        assert result.exit_code == 0
        assert "Validate generated artifacts" in result.stdout
    
    def test_eject_help_text(self):
        """Test eject command help text"""
        result = runner.invoke(app, ["eject", "--help"])
        
        assert result.exit_code == 0
        assert "Eject scripts and pipeline" in result.stdout
        assert "break-glass" in result.stdout
    
    def test_version_help_text(self):
        """Test version command help text"""
        result = runner.invoke(app, ["version", "--help"])
        
        assert result.exit_code == 0
        assert "Display CLI version" in result.stdout
