"""GitHub adapter configuration model"""

from pydantic import BaseModel, Field, SecretStr, field_validator
import re


class GitHubConfig(BaseModel):
    """GitHub adapter configuration with validation"""
    
    github_app_id: str = Field(
        ...,
        pattern=r"^\d+$",
        description="GitHub App ID (numbers only)"
    )
    
    github_app_installation_id: str = Field(
        ...,
        pattern=r"^\d+$",
        description="GitHub App Installation ID for your organization"
    )
    
    github_app_private_key: SecretStr = Field(
        ...,
        description="GitHub App RSA private key"
    )
    
    control_plane_repo_url: str = Field(
        ...,
        description="Control plane repository URL (infrastructure/platform manifests)"
    )
    
    data_plane_repo_url: str = Field(
        ...,
        description="Data plane repository URL (tenant/application configs)"
    )
    
    @field_validator("github_app_private_key")
    @classmethod
    def validate_private_key_format(cls, v: SecretStr) -> SecretStr:
        """Validate private key has RSA format"""
        key_value = v.get_secret_value()
        if not key_value.startswith("-----BEGIN RSA PRIVATE KEY-----"):
            raise ValueError("Private key must start with '-----BEGIN RSA PRIVATE KEY-----'")
        if not key_value.rstrip().endswith("-----END RSA PRIVATE KEY-----"):
            raise ValueError("Private key must end with '-----END RSA PRIVATE KEY-----'")
        return v
    
    @field_validator("control_plane_repo_url", "data_plane_repo_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        """Validate GitHub repository URL format and extract org/repo"""
        pattern = r"^https://github\.com/([^/]+)/([^/]+)/?$"
        match = re.match(pattern, v.rstrip('/'))
        if not match:
            raise ValueError(
                "Invalid GitHub repository URL. "
                "Expected format: https://github.com/org/repo"
            )
        
        org, repo = match.groups()
        if not org or not repo:
            raise ValueError("Organization and repository names cannot be empty")
        
        return v.rstrip('/')
