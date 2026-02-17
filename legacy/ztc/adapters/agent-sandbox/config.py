"""Agent Sandbox adapter configuration"""

from pydantic import BaseModel, Field, field_validator


class AgentSandboxConfig(BaseModel):
    """Configuration for Agent Sandbox controller"""
    
    image_registry: str = Field(
        default="us-central1-docker.pkg.dev/k8s-staging-images/agent-sandbox",
        description="Container registry for agent-sandbox controller image"
    )
    image_tag: str = Field(
        default="latest-main",
        description="Image tag for agent-sandbox controller"
    )
    namespace: str = Field(
        default="agent-sandbox-system",
        description="Kubernetes namespace for agent-sandbox controller"
    )
    mode: str = Field(
        default="production",
        description="Deployment mode: production or preview"
    )
    
    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate mode is production or preview"""
        if v not in ["production", "preview"]:
            raise ValueError("mode must be 'production' or 'preview'")
        return v
