"""Integration tests for bootstrap prerequisite validation.

CRITICAL: These tests use REAL infrastructure - no mocking.
- Requires Docker daemon running
- Requires kubectl, kind binaries installed
- Requires platform.yaml with encrypted secrets
- Requires Age key available for secret decryption
"""

import pytest
import os
from pathlib import Path
from workflow_engine.orchestration.bootstrap_prerequisite_checker import (
    BootstrapPrerequisiteChecker,
    PrerequisiteCheckResult
)


@pytest.fixture
def platform_yaml_path():
    """Use real platform.yaml from zerotouch-engine"""
    platform_yaml = Path('zerotouch-engine/platform/platform.yaml')
    if not platform_yaml.exists():
        raise FileNotFoundError(f"platform.yaml not found at {platform_yaml.absolute()} - required for integration tests")
    return platform_yaml


@pytest.mark.integration
class TestBootstrapPrerequisites:
    """Integration tests for bootstrap prerequisite checks using real infrastructure."""
    
    def test_docker_installed_check_uses_real_binary(self, platform_yaml_path):
        """Test Docker installed check against real system."""
        checker = BootstrapPrerequisiteChecker(platform_yaml_path)
        result = checker.check_docker_installed()
        
        assert result.success, f"Docker must be installed: {result.error}"
        assert result.name == "Docker installed"
    
    def test_docker_running_check_uses_real_daemon(self, platform_yaml_path):
        """Test Docker daemon check against real Docker."""
        checker = BootstrapPrerequisiteChecker(platform_yaml_path)
        result = checker.check_docker_running()
        
        assert result.success, f"Docker daemon must be running: {result.error}"
        assert result.name == "Docker running"
    
    def test_docker_socket_access_uses_real_socket(self, platform_yaml_path):
        """Test Docker socket access against real Docker socket."""
        checker = BootstrapPrerequisiteChecker(platform_yaml_path)
        result = checker.check_docker_socket_access()
        
        assert result.success, f"Docker socket must be accessible: {result.error}"
        assert result.name == "Docker socket access"
    
    def test_docker_resources_check_uses_real_docker_info(self, platform_yaml_path):
        """Test Docker resource validation against real Docker daemon."""
        checker = BootstrapPrerequisiteChecker(platform_yaml_path)
        result = checker.check_docker_resources()
        
        assert result.success, f"Docker resources must be sufficient: {result.error}"
        assert result.name == "Docker resources"
    
    def test_kubectl_installed_check_uses_real_binary(self, platform_yaml_path):
        """Test kubectl check against real system."""
        checker = BootstrapPrerequisiteChecker(platform_yaml_path)
        result = checker.check_kubectl_installed()
        
        assert result.success, f"kubectl must be installed: {result.error}"
        assert result.name == "kubectl installed"
    
    def test_kind_installed_check_uses_real_binary(self, platform_yaml_path):
        """Test kind check against real system."""
        checker = BootstrapPrerequisiteChecker(platform_yaml_path)
        result = checker.check_kind_installed()
        
        assert result.success, f"kind must be installed: {result.error}"
        assert result.name == "kind installed"
    
    def test_hetzner_token_check_uses_real_secrets(self, platform_yaml_path):
        """Test Hetzner token validation against real secrets provider."""
        checker = BootstrapPrerequisiteChecker(platform_yaml_path)
        result = checker.check_hetzner_token()
        
        assert result.success, f"Hetzner API token must be available in secrets: {result.error}"
        assert result.name == "Hetzner API token"
    
    def test_github_credentials_check_uses_real_secrets(self, platform_yaml_path):
        """Test GitHub credentials validation against real secrets provider."""
        checker = BootstrapPrerequisiteChecker(platform_yaml_path)
        result = checker.check_github_credentials()
        
        assert result.success, f"GitHub credentials must be available in secrets: {result.error}"
        assert result.name == "GitHub credentials"
    
    def test_check_all_returns_all_results_from_real_system(self, platform_yaml_path):
        """Test that check_all validates against real system."""
        checker = BootstrapPrerequisiteChecker(platform_yaml_path)
        
        all_passed, results = checker.check_all()
        
        # Verify all checks were executed
        assert len(results) == 8
        assert all(isinstance(r, PrerequisiteCheckResult) for r in results)
        
        # If any check failed, report which ones
        if not all_passed:
            failed_checks = [f"{r.name}: {r.error}" for r in results if not r.success]
            pytest.fail(f"Prerequisites not met:\n" + "\n".join(failed_checks))
