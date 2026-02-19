"""Local Path Provisioner adapter configuration model"""

from pydantic import BaseModel, Field


class LocalPathProvisionerConfig(BaseModel):
    """Local Path Provisioner adapter configuration"""
    
    version: str = Field(default="v0.0.28")
    namespace: str = Field(default="local-path-storage")
    mode: str = Field(default="production")
