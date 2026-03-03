"""Platform configuration models for platform.yaml structure."""

from typing import Dict, Any
from pydantic import BaseModel, Field


class PlatformInfo(BaseModel):
    """Platform metadata from platform.yaml."""

    organization: str = Field(..., description="Organization name")
    app_name: str = Field(..., description="Application name")
    lifecycle_engine: str = Field(default="static", description="Infrastructure lifecycle engine: static or declarative")
    management_topology: str | None = Field(default=None, description="Management topology: enterprise or converged (declarative only)")



class PlatformConfig(BaseModel):
    """Complete platform configuration model for platform.yaml."""
    
    version: str = Field(..., description="Configuration version")
    platform: PlatformInfo = Field(..., description="Platform metadata")
    adapters: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Adapter configurations keyed by adapter name"
    )
