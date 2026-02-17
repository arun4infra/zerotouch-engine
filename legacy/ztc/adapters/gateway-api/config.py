"""Gateway API adapter configuration model."""

from pydantic import BaseModel, Field, EmailStr, field_validator


class GatewayAPIConfig(BaseModel):
    """Gateway API adapter configuration."""

    gateway_api_version: str = Field(
        default="v1.4.1",
        pattern=r"^v\d+\.\d+\.\d+$"
    )
    domain: str = Field(
        default="nutgraf.in",
        pattern=r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$"
    )
    email: EmailStr = Field(default="admin@nutgraf.in")
    hetzner_location: str = Field(default="fsn1")
    mode: str = Field(..., pattern=r"^(production|preview)$")

    @field_validator("gateway_api_version")
    @classmethod
    def validate_version_format(cls, v: str) -> str:
        """Validate version follows semantic versioning."""
        if not v.startswith("v"):
            raise ValueError("Version must start with 'v'")
        return v

    @field_validator("domain")
    @classmethod
    def validate_domain_format(cls, v: str) -> str:
        """Validate domain is a valid FQDN."""
        if not v or v == "null":
            raise ValueError("Domain cannot be empty")
        if ".." in v:
            raise ValueError("Domain cannot contain consecutive dots")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate mode is production or preview."""
        if v not in ["production", "preview"]:
            raise ValueError("Mode must be 'production' or 'preview'")
        return v
