"""Cilium network adapter implementation"""

from typing import List, Dict, Any, Type, Optional
from pydantic import BaseModel, Field
from pathlib import Path
from enum import Enum
import yaml

from ztc.adapters.base import (
    PlatformAdapter,
    InputPrompt,
    ScriptReference,
    AdapterOutput,
)
from ztc.interfaces.capabilities import CNIArtifacts, GatewayAPICapability


class BGPConfig(BaseModel):
    """BGP configuration for Cilium"""
    enabled: bool = False
    asn: Optional[int] = Field(None, ge=1, le=4294967295, description="BGP ASN number")


class CiliumConfig(BaseModel):
    """Cilium adapter configuration with validation"""
    version: str
    bgp: BGPConfig = Field(default_factory=BGPConfig)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "version": "v1.18.5",
                "bgp": {
                    "enabled": True,
                    "asn": 64512
                }
            }
        }
    }


class CiliumScripts(str, Enum):
    """Cilium adapter script resources"""
    WAIT_CILIUM = "post_work/wait-cilium.sh"
    WAIT_GATEWAY_API = "post_work/wait-gateway-api.sh"
    VALIDATE_CNI = "validation/validate-cni.sh"


class CiliumAdapter(PlatformAdapter):
    """Cilium network adapter"""
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return CiliumConfig
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Return interactive prompts for Cilium configuration"""
        return [
            InputPrompt(
                name="version",
                prompt="Select Cilium version",
                type="choice",
                choices=["v1.16.x", "v1.17.x", "v1.18.5"],
                default="v1.18.5",
                help_text="Recommended: v1.18.5"
            ),
            InputPrompt(
                name="bgp_enabled",
                prompt="Enable BGP mode?",
                type="boolean",
                default=False,
                help_text="BGP for advanced routing"
            ),
            InputPrompt(
                name="bgp_asn",
                prompt="BGP ASN",
                type="integer",
                default="64512",
                help_text="Required if BGP enabled"
            )
        ]
    
    def get_invalid_fields(self, current_config: Dict, full_platform_context: Dict) -> List[str]:
        """Return fields invalid due to upstream context changes"""
        invalid = []
        
        # Check if OS changed from Talos (affects embedded mode)
        os_adapter = full_platform_context.get("os")
        if os_adapter and os_adapter != "talos":
            # If OS is not Talos, embedded mode config becomes invalid
            if "embedded_mode" in current_config:
                invalid.append("embedded_mode")
        
        return invalid
    
    def pre_work_scripts(self) -> List[ScriptReference]:
        """Cilium has no pre-work scripts"""
        return []
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """Cilium has no bootstrap scripts (manifests embedded in Talos)"""
        return []
    
    def post_work_scripts(self) -> List[ScriptReference]:
        """Return post-work scripts (wait for CNI readiness)"""
        return [
            ScriptReference(
                package="ztc.adapters.cilium.scripts",
                resource=CiliumScripts.WAIT_CILIUM,
                description="Wait for Cilium CNI ready",
                timeout=300
            ),
            ScriptReference(
                package="ztc.adapters.cilium.scripts",
                resource=CiliumScripts.WAIT_GATEWAY_API,
                description="Wait for Gateway API CRDs",
                timeout=300
            )
        ]
    
    def validation_scripts(self) -> List[ScriptReference]:
        """Return verification scripts"""
        return [
            ScriptReference(
                package="ztc.adapters.cilium.scripts",
                resource=CiliumScripts.VALIDATE_CNI,
                description="Verify pod networking",
                timeout=60
            )
        ]
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate Cilium manifests and capability data"""
        config = CiliumConfig(**self.config)
        
        # Render Jinja2 template
        template = self.jinja_env.get_template("cilium/manifests.yaml.j2")
        manifests_content = await template.render_async(
            version=config.version,
            bgp_enabled=config.bgp.enabled,
            bgp_asn=config.bgp.asn if config.bgp.enabled else None
        )
        
        # Create CNI capability
        cni_capability = CNIArtifacts(
            manifests=manifests_content,
            ready=False
        )
        
        # Create Gateway API capability
        gateway_capability = GatewayAPICapability(
            version=config.version,
            crds_embedded=True
        )
        
        return AdapterOutput(
            manifests={
                "manifests.yaml": manifests_content
            },
            stages=[],
            env_vars={},
            capabilities={
                "cni": cni_capability,
                "gateway-api": gateway_capability
            },
            data={
                "manifests": manifests_content,
                "version": config.version
            }
        )
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata"""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        if not metadata_path.exists():
            return {
                "name": "cilium",
                "version": "1.0.0",
                "phase": "networking",
                "selection_group": "network_tool",
                "is_default": True,
                "provides": [
                    {"capability": "cni", "version": "v1.0"},
                    {"capability": "gateway-api", "version": "v1.0"}
                ],
                "requires": [
                    {"capability": "kubernetes-api", "version": "v1.0"}
                ]
            }
        return yaml.safe_load(metadata_path.read_text())
