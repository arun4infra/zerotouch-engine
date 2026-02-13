"""KSOPS adapter configuration model."""

from typing import Optional
from pydantic import BaseModel, Field, SecretStr, field_validator


class KSOPSConfig(BaseModel):
    """KSOPS adapter configuration."""

    # Age encryption key (optional, populated after bootstrap)
    age_public_key: Optional[str] = Field(None, min_length=1)

    # S3 Configuration (secrets use SecretStr)
    s3_access_key: SecretStr = Field(..., min_length=1)
    s3_secret_key: SecretStr = Field(..., min_length=1)
    s3_endpoint: str = Field(..., pattern=r"^https?://")
    s3_region: str = Field(..., min_length=1)
    s3_bucket_name: str = Field(..., min_length=1)

    # GitHub App Configuration (private key uses SecretStr)
    github_app_id: int = Field(..., gt=0)
    github_app_installation_id: int = Field(..., gt=0)
    github_app_private_key: SecretStr = Field(..., min_length=1)

    # Tenant Configuration
    tenant_org_name: str = Field(..., pattern=r"^[a-zA-Z0-9-]+$")
    tenant_repo_name: str = Field(..., pattern=r"^[a-zA-Z0-9-]+$")

    @field_validator("github_app_private_key")
    @classmethod
    def validate_pem_format(cls, v: SecretStr) -> SecretStr:
        """Validate PEM format."""
        secret_value = v.get_secret_value()
        if not secret_value.startswith("-----BEGIN"):
            raise ValueError("Private key must be in PEM format")
        return v
