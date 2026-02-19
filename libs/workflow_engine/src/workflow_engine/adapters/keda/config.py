"""KEDA adapter configuration model."""

from pydantic import BaseModel, Field, field_validator


class KEDAConfig(BaseModel):
    """KEDA adapter configuration."""

    version: str = Field(default="2.18.1", pattern=r"^\d+\.\d+\.\d+$")
    namespace: str = Field(default="keda", min_length=1)
    mode: str = Field(..., pattern=r"^(production|preview)$")

    @field_validator("namespace")
    @classmethod
    def validate_namespace(cls, v: str) -> str:
        """Validate namespace is DNS-compliant."""
        if not v.replace("-", "").isalnum():
            raise ValueError("Namespace must be alphanumeric with hyphens")
        return v
