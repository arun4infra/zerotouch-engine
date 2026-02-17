"""Tests for KSOPS adapter bootstrap lifecycle"""

import pytest
from workflow_engine.adapters.ksops.adapter import KSOPSAdapter


class TestKSOPSAdapterBootstrap:
    """Test bootstrap_scripts() lifecycle phase"""
    
    def test_bootstrap_excludes_github_scripts(self):
        """Test bootstrap_scripts() excludes inject-identities and env-substitution"""
        config = {
            "s3_access_key": "test-key",
            "s3_secret_key": "test-secret",
            "s3_endpoint": "https://fsn1.example.com",
            "s3_region": "fsn1",
            "s3_bucket_name": "test-bucket"
        }
        
        adapter = KSOPSAdapter(config, None)
        bootstrap_scripts = adapter.bootstrap_scripts()
        
        # Verify no GitHub-related scripts
        script_names = [s.resource.value for s in bootstrap_scripts]
        assert not any("inject-identities" in name for name in script_names)
        assert not any("env-substitution" in name for name in script_names)
        assert not any("bootstrap-storage" in name for name in script_names)
    
    def test_bootstrap_returns_four_scripts(self):
        """Test bootstrap_scripts() returns 4 KSOPS-specific scripts"""
        config = {
            "s3_access_key": "test-key",
            "s3_secret_key": "test-secret",
            "s3_endpoint": "https://fsn1.example.com",
            "s3_region": "fsn1",
            "s3_bucket_name": "test-bucket"
        }
        
        adapter = KSOPSAdapter(config, None)
        bootstrap_scripts = adapter.bootstrap_scripts()
        
        assert len(bootstrap_scripts) == 4
