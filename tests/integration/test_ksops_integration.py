"""Integration tests for KSOPS adapter

Tests verify:
1. Adapter discovered by registry
2. Capability contract provides age_public_key
3. Downstream adapters can consume secrets capability
4. Full integration with ZTC engine
"""

import pytest
from unittest.mock import Mock
from ztc.registry.adapter_registry import AdapterRegistry
from ztc.adapters.ksops.adapter import KSOPSAdapter
from ztc.interfaces.capabilities import SecretsManagementCapability


@pytest.fixture
def valid_ksops_config():
    """Valid KSOPS configuration"""
    return {
        "s3_access_key": "test-access-key",
        "s3_secret_key": "test-secret-key",
        "s3_endpoint": "https://s3.example.com",
        "s3_region": "us-east-1",
        "s3_bucket_name": "test-bucket",
        "github_app_id": 123,
        "github_app_installation_id": 456,
        "github_app_private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
        "tenant_org_name": "test-org",
        "tenant_repo_name": "test-repo",
        "age_public_key": "age1test123456789"
    }


class TestAdapterRegistryIntegration:
    """Test KSOPS adapter registry integration"""
    
    def test_adapter_discovered_by_registry(self):
        """Test KSOPS adapter is discovered by registry"""
        registry = AdapterRegistry()
        
        assert "ksops" in registry.list_adapters()
    
    def test_adapter_metadata_loaded(self):
        """Test adapter metadata loaded correctly"""
        registry = AdapterRegistry()
        metadata = registry.get_metadata("ksops")
        
        assert metadata["name"] == "ksops"
        assert metadata["phase"] == "secrets"
        assert metadata["selection_group"] == "secrets_management"
    
    def test_adapter_instantiation_from_registry(self, valid_ksops_config):
        """Test adapter can be instantiated from registry"""
        registry = AdapterRegistry()
        adapter = registry.get_adapter("ksops", valid_ksops_config)
        
        assert isinstance(adapter, KSOPSAdapter)
        assert adapter.name == "ksops"


class TestCapabilityContract:
    """Test secrets-management capability contract"""
    
    def test_capability_contract_structure(self):
        """Test SecretsManagementCapability has required fields"""
        capability = SecretsManagementCapability(
            provider="ksops",
            s3_bucket="test-bucket",
            sops_config_path=".sops.yaml",
            age_public_key="age1test123"
        )
        
        assert capability.provider == "ksops"
        assert capability.s3_bucket == "test-bucket"
        assert capability.age_public_key == "age1test123"
    
    def test_encryption_env_helper(self):
        """Test encryption_env property returns correct environment variables"""
        capability = SecretsManagementCapability(
            provider="ksops",
            s3_bucket="test-bucket",
            sops_config_path=".sops.yaml",
            age_public_key="age1test123"
        )
        
        env = capability.encryption_env
        assert env["SOPS_AGE_RECIPIENTS"] == "age1test123"


class TestDownstreamAdapterIntegration:
    """Test downstream adapters can consume secrets capability"""
    
    def test_downstream_adapter_accesses_age_key(self, valid_ksops_config):
        """Test downstream adapter can access age_public_key from capability"""
        # Simulate KSOPS adapter providing capability
        ksops_adapter = KSOPSAdapter(valid_ksops_config)
        
        # Create capability
        capability = SecretsManagementCapability(
            provider="ksops",
            s3_bucket=valid_ksops_config["s3_bucket_name"],
            sops_config_path=".sops.yaml",
            age_public_key=valid_ksops_config["age_public_key"]
        )
        
        # Downstream adapter consumes capability
        assert capability.age_public_key == "age1test123456789"
        assert capability.encryption_env["SOPS_AGE_RECIPIENTS"] == "age1test123456789"
    
    def test_downstream_adapter_uses_encryption_env(self):
        """Test downstream adapter can use encryption_env for SOPS commands"""
        capability = SecretsManagementCapability(
            provider="ksops",
            s3_bucket="test-bucket",
            sops_config_path=".sops.yaml",
            age_public_key="age1test123"
        )
        
        # Simulate downstream adapter using encryption env
        import os
        env = os.environ.copy()
        env.update(capability.encryption_env)
        
        assert env["SOPS_AGE_RECIPIENTS"] == "age1test123"


class TestCLIExtensionIntegration:
    """Test CLI extension integration"""
    
    def test_adapter_implements_cli_extension(self, valid_ksops_config):
        """Test KSOPS adapter implements CLIExtension"""
        from ztc.adapters.base import CLIExtension
        
        adapter = KSOPSAdapter(valid_ksops_config)
        assert isinstance(adapter, CLIExtension)
    
    def test_cli_category_returns_secret(self, valid_ksops_config):
        """Test get_cli_category() returns 'secret'"""
        adapter = KSOPSAdapter(valid_ksops_config)
        assert adapter.get_cli_category() == "secret"
    
    def test_cli_app_has_commands(self, valid_ksops_config):
        """Test get_cli_app() returns Typer app with commands"""
        adapter = KSOPSAdapter(valid_ksops_config)
        cli_app = adapter.get_cli_app()
        
        assert cli_app is not None
        # Typer stores commands in registered_commands
        command_names = [cmd.name for cmd in cli_app.registered_commands]
        
        expected_commands = [
            "init-secrets",
            "init-service-secrets",
            "generate-secrets",
            "create-dot-env",
            "display-age-key",
            "encrypt-secret",
            "inject-offline-key",
            "recover",
            "rotate-keys"
        ]
        
        for cmd in expected_commands:
            assert cmd in command_names


class TestAdapterMetadata:
    """Test adapter metadata contract"""
    
    def test_metadata_provides_secrets_management(self):
        """Test adapter.yaml declares secrets-management capability"""
        registry = AdapterRegistry()
        metadata = registry.get_metadata("ksops")
        
        provides = metadata.get("provides", [])
        # Handle both dict and string formats
        capability_names = [
            p["capability"] if isinstance(p, dict) else p
            for p in provides
        ]
        assert "secrets-management" in capability_names
    
    def test_metadata_requires_kubernetes_api(self):
        """Test adapter.yaml declares kubernetes-api requirement"""
        registry = AdapterRegistry()
        metadata = registry.get_metadata("ksops")
        
        requires = metadata.get("requires", [])
        # Handle both dict and string formats
        capability_names = [
            r["capability"] if isinstance(r, dict) else r
            for r in requires
        ]
        assert "kubernetes-api" in capability_names
    
    def test_metadata_has_version(self):
        """Test adapter.yaml has version field"""
        registry = AdapterRegistry()
        metadata = registry.get_metadata("ksops")
        
        assert "version" in metadata
        assert metadata["version"] == "1.0.0"
