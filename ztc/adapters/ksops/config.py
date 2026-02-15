"""KSOPS adapter configuration model."""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class KSOPSConfig(BaseModel):
    """KSOPS adapter configuration (GitHub fields removed - now in GitHub adapter)."""
    
    model_config = ConfigDict(extra='forbid')

    # Age encryption key (optional, populated after bootstrap)
    age_public_key: Optional[str] = Field(None, min_length=1)

    # S3 Configuration (secrets use SecretStr)
    s3_access_key: SecretStr = Field(..., min_length=1)
    s3_secret_key: SecretStr = Field(..., min_length=1)
    s3_endpoint: str = Field(..., pattern=r"^https?://")
    s3_region: str = Field(..., min_length=1)
    s3_bucket_name: str = Field(..., min_length=1)
