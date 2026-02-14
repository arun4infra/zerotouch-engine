"""External-DNS adapter configuration model"""

from pydantic import BaseModel, Field, field_validator


class ExternalDNSConfig(BaseModel):
    """External-DNS adapter configuration"""
    
    version: str = Field(
        ...,
        description="External-DNS Helm chart version"
    )
    namespace: str = Field(
        default="external-dns",
        description="Kubernetes namespace for External-DNS"
    )
    provider: str = Field(
        ...,
        description="DNS provider (hetzner or aws)"
    )
    mode: str = Field(
        ...,
        description="Deployment mode (production or preview)"
    )
    
    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate provider is hetzner or aws"""
        if v not in ["hetzner", "aws"]:
            raise ValueError("Provider must be 'hetzner' or 'aws'")
        return v
    
    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate mode is production or preview"""
        if v not in ["production", "preview"]:
            raise ValueError("Mode must be 'production' or 'preview'")
        return v
