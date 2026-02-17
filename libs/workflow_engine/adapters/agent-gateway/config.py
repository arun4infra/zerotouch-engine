"""Agent Gateway adapter configuration"""

from pydantic import BaseModel, Field, field_validator


class AgentGatewayConfig(BaseModel):
    """Configuration for Agent Gateway routing and authentication"""
    
    image_tag: str = Field(
        default="latest",
        description="Image tag for agent-gateway service"
    )
    namespace: str = Field(
        default="platform-agent-gateway",
        description="Kubernetes namespace for agent-gateway"
    )
    domain: str = Field(
        default="agentgateway.nutgraf.in",
        description="Domain for agent-gateway routing"
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
