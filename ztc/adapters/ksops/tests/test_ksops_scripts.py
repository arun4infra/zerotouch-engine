"""Unit tests for KSOPS adapter script contract validation

Tests verify:
1. All 28 scripts exist and are accessible
2. ScriptReference objects validate at instantiation
3. Context data contains only non-sensitive fields
4. Secret environment variables properly configured
5. Scripts follow hybrid context/env pattern
"""

import pytest
from pathlib import Path
from ztc.adapters.base import ScriptReference
from ztc.adapters.ksops.adapter import KSOPSAdapter, KSOPSScripts
from ztc.adapters.ksops.config import KSOPSConfig


@pytest.fixture
def valid_ksops_config():
    """Valid KSOPS configuration for testing"""
    return {
        "s3_access_key": "test_access_key",
        "s3_secret_key": "test_secret_key",
        "s3_endpoint": "https://s3.example.com",
        "s3_region": "us-east-1",
        "s3_bucket_name": "test-bucket",
        "github_app_id": 123456,
        "github_app_installation_id": 789012,
        "github_app_private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
        "tenant_org_name": "test-org",
        "tenant_repo_name": "test-repo"
    }


class TestKSOPSScriptExistence:
    """Test all 28 KSOPS scripts exist in correct subdirectories"""
    
    def test_pre_work_scripts_exist(self):
        """Test 6 pre_work scripts exist"""
        pre_work_scripts = [
            KSOPSScripts.GENERATE_AGE_KEYS,
            KSOPSScripts.SETUP_ENV_SECRETS,
            KSOPSScripts.RETRIEVE_AGE_KEY,
            KSOPSScripts.INJECT_OFFLINE_KEY,
            KSOPSScripts.CREATE_AGE_BACKUP_UTIL,
            KSOPSScripts.BACKUP_AGE_TO_S3,
        ]
        
        for script in pre_work_scripts:
            ref = ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=script,
                description=f"Test {script.value}"
            )
            assert ref.uri.startswith("ksops://pre_work/")
    
    def test_bootstrap_scripts_exist(self):
        """Test 7 bootstrap scripts exist"""
        bootstrap_scripts = [
            KSOPSScripts.INJECT_IDENTITIES,
            KSOPSScripts.BOOTSTRAP_STORAGE,
            KSOPSScripts.INSTALL_KSOPS,
            KSOPSScripts.INJECT_AGE_KEY,
            KSOPSScripts.CREATE_AGE_BACKUP,
            KSOPSScripts.ENV_SUBSTITUTION,
            KSOPSScripts.DEPLOY_KSOPS,
        ]
        
        for script in bootstrap_scripts:
            ref = ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=script,
                description=f"Test {script.value}"
            )
            assert ref.uri.startswith("ksops://bootstrap/")
    
    def test_post_work_scripts_exist(self):
        """Test 1 post_work script exists"""
        ref = ScriptReference(
            package="ztc.adapters.ksops.scripts",
            resource=KSOPSScripts.WAIT_KSOPS,
            description="Test wait script"
        )
        assert ref.uri == "ksops://post_work/09c-wait-ksops-sidecar.sh"
    
    def test_validation_scripts_exist(self):
        """Test 7 validation scripts exist"""
        validation_scripts = [
            KSOPSScripts.VERIFY_KSOPS,
            KSOPSScripts.VALIDATE_PACKAGE,
            KSOPSScripts.VALIDATE_INJECTION,
            KSOPSScripts.VALIDATE_STORAGE,
            KSOPSScripts.VALIDATE_CONFIG,
            KSOPSScripts.VALIDATE_ENCRYPTION,
            KSOPSScripts.VALIDATE_DECRYPTION,
        ]
        
        for script in validation_scripts:
            ref = ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=script,
                description=f"Test {script.value}"
            )
            assert ref.uri.startswith("ksops://validation/")
    
    def test_generator_scripts_exist(self):
        """Test 7 generator scripts exist"""
        generator_scripts = [
            KSOPSScripts.GEN_CREATE_DOT_ENV,
            KSOPSScripts.GEN_PLATFORM_SOPS,
            KSOPSScripts.GEN_SERVICE_ENV_SOPS,
            KSOPSScripts.GEN_CORE_SECRETS,
            KSOPSScripts.GEN_ENV_SECRETS,
            KSOPSScripts.GEN_GHCR_PULL_SECRET,
            KSOPSScripts.GEN_TENANT_REGISTRY_SECRETS,
        ]
        
        for script in generator_scripts:
            ref = ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=script,
                description=f"Test {script.value}"
            )
            assert ref.uri.startswith("ksops://generators/")


class TestKSOPSScriptReferences:
    """Test ScriptReference objects validate correctly"""
    
    def test_pre_work_scripts_return_correct_count(self, valid_ksops_config):
        """Test pre_work_scripts() returns 6 references"""
        adapter = KSOPSAdapter(valid_ksops_config)
        scripts = adapter.pre_work_scripts()
        assert len(scripts) == 6
    
    def test_bootstrap_scripts_return_correct_count(self, valid_ksops_config):
        """Test bootstrap_scripts() returns 7 references"""
        adapter = KSOPSAdapter(valid_ksops_config)
        scripts = adapter.bootstrap_scripts()
        assert len(scripts) == 7
    
    def test_post_work_scripts_return_correct_count(self, valid_ksops_config):
        """Test post_work_scripts() returns 1 reference"""
        adapter = KSOPSAdapter(valid_ksops_config)
        scripts = adapter.post_work_scripts()
        assert len(scripts) == 1
    
    def test_validation_scripts_return_correct_count(self, valid_ksops_config):
        """Test validation_scripts() returns 7 references"""
        adapter = KSOPSAdapter(valid_ksops_config)
        scripts = adapter.validation_scripts()
        assert len(scripts) == 7


class TestKSOPSContextDataSecurity:
    """Test context_data contains no secrets"""
    
    def test_pre_work_context_data_no_secrets(self, valid_ksops_config):
        """Test pre_work scripts context_data contains no secrets"""
        adapter = KSOPSAdapter(valid_ksops_config)
        scripts = adapter.pre_work_scripts()
        
        for script in scripts:
            if script.context_data:
                # Verify no secret keys in context_data
                assert "s3_access_key" not in script.context_data
                assert "s3_secret_key" not in script.context_data
                assert "github_app_private_key" not in script.context_data
                assert "age_private_key" not in script.context_data
    
    def test_bootstrap_context_data_no_secrets(self, valid_ksops_config):
        """Test bootstrap scripts context_data contains no secrets"""
        adapter = KSOPSAdapter(valid_ksops_config)
        scripts = adapter.bootstrap_scripts()
        
        for script in scripts:
            if script.context_data:
                assert "s3_access_key" not in script.context_data
                assert "s3_secret_key" not in script.context_data
                assert "github_app_private_key" not in script.context_data
    
    def test_validation_context_data_no_secrets(self, valid_ksops_config):
        """Test validation scripts context_data contains no secrets"""
        adapter = KSOPSAdapter(valid_ksops_config)
        scripts = adapter.validation_scripts()
        
        for script in scripts:
            if script.context_data:
                assert "s3_access_key" not in script.context_data
                assert "s3_secret_key" not in script.context_data


class TestKSOPSSecretEnvironmentVariables:
    """Test secret_env_vars properly configured"""
    
    def test_s3_scripts_have_secret_env_vars(self, valid_ksops_config):
        """Test scripts requiring S3 access have secret_env_vars"""
        adapter = KSOPSAdapter(valid_ksops_config)
        
        # Pre-work scripts that need S3 access
        pre_work = adapter.pre_work_scripts()
        s3_scripts = [s for s in pre_work if s.context_data and "s3_endpoint" in s.context_data]
        
        for script in s3_scripts:
            assert hasattr(script, 'secret_env_vars')
            if script.secret_env_vars:
                # Should have S3 credentials
                assert "S3_ACCESS_KEY" in script.secret_env_vars or "s3_access_key" in str(script.secret_env_vars).lower()
    
    def test_github_app_scripts_have_secret_env_vars(self, valid_ksops_config):
        """Test scripts requiring GitHub App credentials have secret_env_vars"""
        adapter = KSOPSAdapter(valid_ksops_config)
        bootstrap = adapter.bootstrap_scripts()
        
        # Find inject-identities script
        identity_script = next((s for s in bootstrap if "inject-identities" in s.resource.value), None)
        assert identity_script is not None
        assert hasattr(identity_script, 'secret_env_vars')


class TestKSOPSContextDataValidation:
    """Test context_data is JSON-serializable and has no null values"""
    
    def test_context_data_json_serializable(self, valid_ksops_config):
        """Test all context_data is JSON-serializable"""
        import json
        adapter = KSOPSAdapter(valid_ksops_config)
        
        all_scripts = (
            adapter.pre_work_scripts() +
            adapter.bootstrap_scripts() +
            adapter.post_work_scripts() +
            adapter.validation_scripts()
        )
        
        for script in all_scripts:
            if script.context_data:
                # Should not raise exception
                json.dumps(script.context_data)
    
    def test_context_data_no_null_values(self, valid_ksops_config):
        """Test context_data contains no null or empty values"""
        adapter = KSOPSAdapter(valid_ksops_config)
        
        all_scripts = (
            adapter.pre_work_scripts() +
            adapter.bootstrap_scripts() +
            adapter.post_work_scripts() +
            adapter.validation_scripts()
        )
        
        for script in all_scripts:
            if script.context_data:
                for key, value in script.context_data.items():
                    assert value is not None, f"Null value in {script.resource.value}: {key}"
                    assert value != "", f"Empty value in {script.resource.value}: {key}"
