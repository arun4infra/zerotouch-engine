"""NATS adapter configuration model"""

from pydantic import BaseModel, Field, field_validator


class NATSConfig(BaseModel):
    """NATS adapter configuration"""
    
    version: str = Field(
        default="1.2.6",
        description="NATS Helm chart version"
    )
    namespace: str = Field(
        default="nats",
        description="Kubernetes namespace for NATS"
    )
    jetstream_file_store_size: str = Field(
        default="10Gi",
        description="JetStream file store size"
    )
    jetstream_memory_store_size: str = Field(
        default="1Gi",
        description="JetStream memory store size"
    )
    mode: str = Field(
        ...,
        description="Deployment mode (production or preview)"
    )
    
    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version format"""
        import re
        if not re.match(r"^\d+\.\d+\.\d+$", v):
            raise ValueError("Version must match pattern X.Y.Z")
        return v
    
    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate mode is production or preview"""
        if v not in ["production", "preview"]:
            raise ValueError("Mode must be 'production' or 'preview'")
        return v
