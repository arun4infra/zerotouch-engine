"""Tests for KSOPS adapter configuration (S3-only, no GitHub fields)"""

import pytest
from pydantic import ValidationError
from workflow_engine.adapters.ksops.config import KSOPSConfig


class TestKSOPSConfigWithoutGitHub:
    """Test KSOPS config rejects GitHub fields and accepts S3-only"""
    
    def test_config_accepts_s3_only_fields(self):
        """Test KSOPSConfig accepts S3-only configuration"""
        config = {
            "s3_access_key": "test-key",
            "s3_secret_key": "test-secret",
            "s3_endpoint": "https://fsn1.example.com",
            "s3_region": "fsn1",
            "s3_bucket_name": "test-bucket"
        }
        
        ksops_config = KSOPSConfig(**config)
        assert ksops_config.s3_endpoint == "https://fsn1.example.com"
        assert ksops_config.s3_region == "fsn1"
        assert ksops_config.s3_bucket_name == "test-bucket"
    
    def test_config_rejects_github_app_id(self):
        """Test KSOPSConfig rejects github_app_id field"""
        config = {
            "s3_access_key": "test-key",
            "s3_secret_key": "test-secret",
            "s3_endpoint": "https://fsn1.example.com",
            "s3_region": "fsn1",
            "s3_bucket_name": "test-bucket",
            "github_app_id": "123456"
        }
        
        with pytest.raises((ValidationError, TypeError)):
            KSOPSConfig(**config)
    
    def test_config_rejects_tenant_org_name(self):
        """Test KSOPSConfig rejects tenant_org_name field"""
        config = {
            "s3_access_key": "test-key",
            "s3_secret_key": "test-secret",
            "s3_endpoint": "https://fsn1.example.com",
            "s3_region": "fsn1",
            "s3_bucket_name": "test-bucket",
            "tenant_org_name": "test-org"
        }
        
        with pytest.raises((ValidationError, TypeError)):
            KSOPSConfig(**config)
