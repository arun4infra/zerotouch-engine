"""Tests for GitHub adapter init lifecycle"""

import pytest
from ztc.adapters.github.adapter import GithubAdapter


class TestGitHubAdapterInit:
    """Test init() lifecycle phase"""
    
    def test_init_returns_validate_access_script(self):
        """Test init() returns validate-github-access script"""
        config = {
            "github_app_id": "123456",
            "github_app_installation_id": "789012",
            "github_app_private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
            "tenant_repo_url": "https://github.com/test-org/test-repo"
        }
        
        adapter = GithubAdapter(config, None)
        init_scripts = adapter.init()
        
        assert len(init_scripts) == 1
        assert "validate-github-access" in init_scripts[0].resource.value
    
    def test_init_script_context_data(self):
        """Test init script receives correct context_data"""
        config = {
            "github_app_id": "123456",
            "github_app_installation_id": "789012",
            "github_app_private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
            "tenant_repo_url": "https://github.com/test-org/test-repo"
        }
        
        adapter = GithubAdapter(config, None)
        script_ref = adapter.init()[0]
        
        assert script_ref.context_data["github_app_id"] == "123456"
        assert script_ref.context_data["github_app_installation_id"] == "789012"
        assert script_ref.context_data["tenant_org"] == "test-org"
        assert script_ref.context_data["tenant_repo"] == "test-repo"
    
    def test_init_script_secret_env_vars(self):
        """Test init script receives private key via secret_env_vars"""
        config = {
            "github_app_id": "123456",
            "github_app_installation_id": "789012",
            "github_app_private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
            "tenant_repo_url": "https://github.com/test-org/test-repo"
        }
        
        adapter = GithubAdapter(config, None)
        script_ref = adapter.init()[0]
        
        assert "GITHUB_APP_PRIVATE_KEY" in script_ref.secret_env_vars
        assert "-----BEGIN RSA PRIVATE KEY-----" in script_ref.secret_env_vars["GITHUB_APP_PRIVATE_KEY"]
