"""Tests for KSOPS adapter init lifecycle"""

import pytest
from workflow_engine.adapters.ksops.adapter import KSOPSAdapter


class TestKSOPSAdapterInit:
    """Test init() lifecycle phase"""
    
    def test_init_returns_setup_env_secrets_script(self):
        """Test init() returns setup-env-secrets script"""
        config = {
            "s3_access_key": "test-key",
            "s3_secret_key": "test-secret",
            "s3_endpoint": "https://fsn1.example.com",
            "s3_region": "fsn1",
            "s3_bucket_name": "test-bucket"
        }
        
        adapter = KSOPSAdapter(config, None)
        init_scripts = adapter.init()
        
        assert len(init_scripts) == 1
        assert "setup-env-secrets" in init_scripts[0].resource.value
    
    def test_init_script_context_data(self):
        """Test init script receives correct S3 context_data"""
        config = {
            "s3_access_key": "test-key",
            "s3_secret_key": "test-secret",
            "s3_endpoint": "https://fsn1.example.com",
            "s3_region": "fsn1",
            "s3_bucket_name": "test-bucket"
        }
        
        adapter = KSOPSAdapter(config, None)
        script_ref = adapter.init()[0]
        
        assert script_ref.context_data["s3_endpoint"] == "https://fsn1.example.com"
        assert script_ref.context_data["s3_region"] == "fsn1"
        assert script_ref.context_data["s3_bucket_name"] == "test-bucket"
    
    def test_init_script_secret_env_vars(self):
        """Test init script receives S3 credentials via secret_env_vars"""
        config = {
            "s3_access_key": "test-key",
            "s3_secret_key": "test-secret",
            "s3_endpoint": "https://fsn1.example.com",
            "s3_region": "fsn1",
            "s3_bucket_name": "test-bucket"
        }
        
        adapter = KSOPSAdapter(config, None)
        script_ref = adapter.init()[0]
        
        assert "S3_ACCESS_KEY" in script_ref.secret_env_vars
        assert "S3_SECRET_KEY" in script_ref.secret_env_vars
