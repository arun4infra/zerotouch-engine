"""ArgoCD adapter configuration model."""

from pydantic import BaseModel, Field, SecretStr, field_validator


class ArgoCDConfig(BaseModel):
    """ArgoCD adapter configuration."""

    version: str = Field(..., pattern=r"^v\d+\.\d+\.\d+$")
    namespace: str = Field(default="argocd", min_length=1)
    platform_repo_url: str = Field(..., pattern=r"^https://github\.com/.+\.git$")
    platform_repo_branch: str = Field(default="main", min_length=1)
    overlay_environment: str = Field(..., pattern=r"^(main|preview|dev)$")
    admin_password: SecretStr = Field(default=None)
    mode: str = Field(default="production", pattern=r"^(production|preview)$")

    @field_validator("version")
    @classmethod
    def validate_version_format(cls, v: str) -> str:
        """Validate version follows semantic versioning."""
        if not v.startswith("v"):
            raise ValueError("Version must start with 'v'")
        return v

    @field_validator("namespace")
    @classmethod
    def validate_namespace(cls, v: str) -> str:
        """Validate namespace is DNS-compliant."""
        if not v.replace("-", "").isalnum():
            raise ValueError("Namespace must be alphanumeric with hyphens")
        return v
