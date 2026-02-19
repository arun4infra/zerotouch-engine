"""Cert-manager adapter configuration model."""

from pydantic import BaseModel, Field, field_validator


class CertManagerConfig(BaseModel):
    """Cert-manager adapter configuration."""

    version: str = Field(default="v1.19.2", pattern=r"^v?\d+\.\d+\.\d+$")
    namespace: str = Field(default="cert-manager", min_length=1)
    enable_gateway_api: bool = Field(default=True)
    mode: str = Field(..., pattern=r"^(production|preview)$")

    @field_validator("version")
    @classmethod
    def validate_version_format(cls, v: str) -> str:
        """Validate version follows semantic versioning."""
        if not v.startswith("v"):
            v = f"v{v}"
        return v

    @field_validator("namespace")
    @classmethod
    def validate_namespace(cls, v: str) -> str:
        """Validate namespace is DNS-compliant."""
        if not v.replace("-", "").isalnum():
            raise ValueError("Namespace must be alphanumeric with hyphens")
        return v
