"""Crossplane adapter configuration model."""

from pydantic import BaseModel, Field, field_validator
from typing import List


class CrossplaneConfig(BaseModel):
    """Crossplane adapter configuration."""

    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    namespace: str = Field(default="crossplane-system", min_length=1)
    enable_composition_revisions: bool = Field(default=True)
    mode: str = Field(..., pattern=r"^(production|preview)$")
    providers: List[str] = Field(default_factory=lambda: ["kubernetes"])
    
    @field_validator("providers", mode="before")
    @classmethod
    def parse_providers(cls, v):
        """Parse providers from string or list"""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except:
                return [v]
        return v if v else ["kubernetes"]

    @field_validator("version")
    @classmethod
    def validate_version_format(cls, v: str) -> str:
        """Validate version follows semantic versioning."""
        parts = v.split(".")
        if len(parts) != 3:
            raise ValueError("Version must follow semantic versioning (X.Y.Z)")
        for part in parts:
            if not part.isdigit():
                raise ValueError("Version parts must be numeric")
        return v

    @field_validator("namespace")
    @classmethod
    def validate_namespace(cls, v: str) -> str:
        """Validate namespace is DNS-compliant."""
        if not v.replace("-", "").isalnum():
            raise ValueError("Namespace must be alphanumeric with hyphens")
        return v

    @field_validator("providers")
    @classmethod
    def validate_providers(cls, v: List[str]) -> List[str]:
        """Validate providers list is not empty and contains valid provider names."""
        if not v:
            raise ValueError("Providers list cannot be empty")
        valid_providers = {"kubernetes", "aws", "hetzner"}
        for provider in v:
            if provider not in valid_providers:
                raise ValueError(f"Invalid provider: {provider}. Must be one of {valid_providers}")
        return v
