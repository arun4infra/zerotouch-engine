"""Tests for GitHub adapter bootstrap lifecycle"""

import pytest
from ztc.adapters.github.adapter import GithubAdapter


class TestGitHubAdapterBootstrap:
    """Test bootstrap_scripts() lifecycle phase"""
    
    def test_bootstrap_returns_two_scripts(self):
        """Test bootstrap_scripts() returns inject-identities and env-substitution"""
        config = {
            "github_app_id": "123456",
            "github_app_installation_id": "789012",
            "github_app_private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
            "tenant_org_name": "test-org",
            "tenant_repo_name": "test-repo"
        }
        
        adapter = GithubAdapter(config, None)
        bootstrap_scripts = adapter.bootstrap_scripts()
        
        assert len(bootstrap_scripts) == 2
        assert "inject-identities" in bootstrap_scripts[0].resource.value
        assert "env-substitution" in bootstrap_scripts[1].resource.value
    
    def test_inject_identities_context_data(self):
        """Test inject-identities script receives correct context_data"""
        config = {
            "github_app_id": "123456",
            "github_app_installation_id": "789012",
            "github_app_private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
            "tenant_org_name": "test-org",
            "tenant_repo_name": "test-repo"
        }
        
        adapter = GithubAdapter(config, None)
        inject_script = adapter.bootstrap_scripts()[0]
        
        assert inject_script.context_data["github_app_id"] == "123456"
        assert inject_script.context_data["github_app_installation_id"] == "789012"
        assert "GITHUB_APP_PRIVATE_KEY" in inject_script.secret_env_vars
    
    def test_env_substitution_context_data(self):
        """Test env-substitution script receives correct context_data"""
        config = {
            "github_app_id": "123456",
            "github_app_installation_id": "789012",
            "github_app_private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
            "tenant_org_name": "test-org",
            "tenant_repo_name": "test-repo"
        }
        
        adapter = GithubAdapter(config, None)
        env_sub_script = adapter.bootstrap_scripts()[1]
        
        assert env_sub_script.context_data["tenant_org_name"] == "test-org"
        assert env_sub_script.context_data["tenant_repo_name"] == "test-repo"
