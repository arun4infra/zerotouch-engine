"""Unit tests for KSOPS configuration models.

Tests verify:
1. KSOPSConfig validates all required fields
2. SecretStr fields mask values properly
3. Invalid configurations raise ValidationError with field details
4. KSOPSOutputData rejects SecretStr types
"""

import pytest
from pydantic import ValidationError, SecretStr

from ztc.adapters.ksops.config import KSOPSConfig
from ztc.adapters.ksops.output import KSOPSOutputData


class TestKSOPSConfigValidation:
    """Test KSOPSConfig Pydantic model validation."""

    def test_valid_configuration_passes(self):
        """Test valid configuration passes validation."""
        valid_config = {
            "s3_access_key": "test_access_key",
            "s3_secret_key": "test_secret_key",
            "s3_endpoint": "https://fsn1.your-objectstorage.com",
            "s3_region": "fsn1",
            "s3_bucket_name": "test-bucket",
            "github_app_id": 123456,
            "github_app_installation_id": 789012,
            "github_app_private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
            "tenant_org_name": "test-org",
            "tenant_repo_name": "test-repo",
        }
        
        config = KSOPSConfig(**valid_config)
        
        assert config.s3_endpoint == "https://fsn1.your-objectstorage.com"
        assert config.s3_region == "fsn1"
        assert config.s3_bucket_name == "test-bucket"
        assert config.github_app_id == 123456
        assert config.github_app_installation_id == 789012
        assert config.tenant_org_name == "test-org"
        assert config.tenant_repo_name == "test-repo"

    def test_secret_str_fields_mask_values(self):
        """Test SecretStr fields mask values in logs."""
        valid_config = {
            "s3_access_key": "test_access_key",
            "s3_secret_key": "test_secret_key",
            "s3_endpoint": "https://fsn1.your-objectstorage.com",
            "s3_region": "fsn1",
            "s3_bucket_name": "test-bucket",
            "github_app_id": 123456,
            "github_app_installation_id": 789012,
            "github_app_private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
            "tenant_org_name": "test-org",
            "tenant_repo_name": "test-repo",
        }
        
        config = KSOPSConfig(**valid_config)
        
        # SecretStr fields should be masked
        assert isinstance(config.s3_access_key, SecretStr)
        assert isinstance(config.s3_secret_key, SecretStr)
        assert isinstance(config.github_app_private_key, SecretStr)
        
        # Get actual values
        assert config.s3_access_key.get_secret_value() == "test_access_key"
        assert config.s3_secret_key.get_secret_value() == "test_secret_key"
        assert "-----BEGIN RSA PRIVATE KEY-----" in config.github_app_private_key.get_secret_value()
        
        # String representation should mask secrets
        config_str = str(config)
        assert "test_access_key" not in config_str
        assert "test_secret_key" not in config_str

    def test_invalid_s3_endpoint_raises_error(self):
        """Test invalid S3 endpoint raises ValidationError."""
        invalid_config = {
            "s3_access_key": "test_access_key",
            "s3_secret_key": "test_secret_key",
            "s3_endpoint": "not-a-url",  # Invalid
            "s3_region": "fsn1",
            "s3_bucket_name": "test-bucket",
            "github_app_id": 123456,
            "github_app_installation_id": 789012,
            "github_app_private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
            "tenant_org_name": "test-org",
            "tenant_repo_name": "test-repo",
        }
        
        with pytest.raises(ValidationError) as exc_info:
            KSOPSConfig(**invalid_config)
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("s3_endpoint",) for error in errors)

    def test_negative_github_app_id_raises_error(self):
        """Test negative GitHub App ID raises ValidationError."""
        invalid_config = {
            "s3_access_key": "test_access_key",
            "s3_secret_key": "test_secret_key",
            "s3_endpoint": "https://fsn1.your-objectstorage.com",
            "s3_region": "fsn1",
            "s3_bucket_name": "test-bucket",
            "github_app_id": -1,  # Invalid
            "github_app_installation_id": 789012,
            "github_app_private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
            "tenant_org_name": "test-org",
            "tenant_repo_name": "test-repo",
        }
        
        with pytest.raises(ValidationError) as exc_info:
            KSOPSConfig(**invalid_config)
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("github_app_id",) for error in errors)

    def test_non_pem_private_key_raises_error(self):
        """Test non-PEM private key raises ValidationError."""
        invalid_config = {
            "s3_access_key": "test_access_key",
            "s3_secret_key": "test_secret_key",
            "s3_endpoint": "https://fsn1.your-objectstorage.com",
            "s3_region": "fsn1",
            "s3_bucket_name": "test-bucket",
            "github_app_id": 123456,
            "github_app_installation_id": 789012,
            "github_app_private_key": "not-a-pem-key",  # Invalid
            "tenant_org_name": "test-org",
            "tenant_repo_name": "test-repo",
        }
        
        with pytest.raises(ValidationError) as exc_info:
            KSOPSConfig(**invalid_config)
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("github_app_private_key",) for error in errors)
        assert any("PEM format" in str(error["msg"]) for error in errors)

    def test_invalid_tenant_org_name_pattern_raises_error(self):
        """Test invalid tenant org name pattern raises ValidationError."""
        invalid_config = {
            "s3_access_key": "test_access_key",
            "s3_secret_key": "test_secret_key",
            "s3_endpoint": "https://fsn1.your-objectstorage.com",
            "s3_region": "fsn1",
            "s3_bucket_name": "test-bucket",
            "github_app_id": 123456,
            "github_app_installation_id": 789012,
            "github_app_private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
            "tenant_org_name": "invalid_org!",  # Invalid characters
            "tenant_repo_name": "test-repo",
        }
        
        with pytest.raises(ValidationError) as exc_info:
            KSOPSConfig(**invalid_config)
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("tenant_org_name",) for error in errors)

    def test_missing_required_field_raises_error(self):
        """Test missing required field raises ValidationError."""
        incomplete_config = {
            "s3_access_key": "test_access_key",
            "s3_secret_key": "test_secret_key",
            # Missing s3_endpoint
            "s3_region": "fsn1",
            "s3_bucket_name": "test-bucket",
            "github_app_id": 123456,
            "github_app_installation_id": 789012,
            "github_app_private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
            "tenant_org_name": "test-org",
            "tenant_repo_name": "test-repo",
        }
        
        with pytest.raises(ValidationError) as exc_info:
            KSOPSConfig(**incomplete_config)
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("s3_endpoint",) for error in errors)


class TestKSOPSOutputDataValidation:
    """Test KSOPSOutputData model validation."""

    def test_valid_output_data_passes(self):
        """Test valid output data passes validation."""
        valid_output = {
            "s3_bucket": "test-bucket",
            "tenant_org": "test-org",
            "tenant_repo": "test-repo",
        }
        
        output = KSOPSOutputData(**valid_output)
        
        assert output.s3_bucket == "test-bucket"
        assert output.tenant_org == "test-org"
        assert output.tenant_repo == "test-repo"

    def test_extra_fields_rejected(self):
        """Test extra='forbid' rejects unknown fields."""
        invalid_output = {
            "s3_bucket": "test-bucket",
            "tenant_org": "test-org",
            "tenant_repo": "test-repo",
            "extra_field": "should-fail",  # Unknown field
        }
        
        with pytest.raises(ValidationError) as exc_info:
            KSOPSOutputData(**invalid_output)
        
        errors = exc_info.value.errors()
        assert any("extra_field" in str(error) for error in errors)

    def test_secret_str_rejected_in_output(self):
        """Test SecretStr types are rejected in output data."""
        # SecretStr is rejected at type validation level (before field validator)
        invalid_output = {
            "s3_bucket": SecretStr("test-bucket"),
            "tenant_org": "test-org",
            "tenant_repo": "test-repo",
        }
        
        with pytest.raises(ValidationError) as exc_info:
            KSOPSOutputData(**invalid_output)
        
        errors = exc_info.value.errors()
        # Pydantic rejects SecretStr at type level with 'string_type' error
        assert any(error["loc"] == ("s3_bucket",) and error["type"] == "string_type" for error in errors)
