"""Platform configuration models for platform.yaml structure."""

from typing import Dict, Any
from pydantic import BaseModel, Field


class PlatformInfo(BaseModel):
    """Platform metadata from platform.yaml."""
    
    organization: str = Field(..., description="Organization name")
    app_name: str = Field(..., description="Application name")


class PlatformConfig(BaseModel):
    """Complete platform configuration model for platform.yaml."""
    
    version: str = Field(..., description="Configuration version")
    platform: PlatformInfo = Field(..., description="Platform metadata")
    adapters: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Adapter configurations keyed by adapter name"
    )
