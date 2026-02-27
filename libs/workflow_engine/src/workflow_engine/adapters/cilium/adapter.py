"""Cilium network adapter implementation"""

from typing import List, Dict, Any, Type, Optional
from pydantic import BaseModel, Field
from pathlib import Path
from enum import Enum
import yaml

from workflow_engine.adapters.base import (
    PlatformAdapter,
    InputPrompt,
    ScriptReference,
    AdapterOutput,
)
from workflow_engine.interfaces.capabilities import CNIArtifacts, GatewayAPICapability


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
    WAIT_GATEWAY_API = "post_work/wait-gateway_api.sh"
    VALIDATE_CNI = "validation/validate-cni.sh"


class CiliumAdapter(PlatformAdapter):
    """Cilium network adapter"""
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return CiliumConfig
    
    def init(self) -> List[ScriptReference]:
        """Cilium adapter has no init scripts"""
        return []
    
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
    
    def should_skip_field(self, field_name: str, current_config: Dict[str, Any]) -> bool:
        """Skip bgp_asn if BGP not enabled"""
        if field_name == "bgp_asn" and not current_config.get("bgp_enabled", False):
            return True
        return False
    
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
                package="workflow_engine.adapters.cilium.scripts",
                resource=CiliumScripts.WAIT_CILIUM,
                description="Wait for Cilium CNI ready",
                timeout=300
            ),
            ScriptReference(
                package="workflow_engine.adapters.cilium.scripts",
                resource=CiliumScripts.WAIT_GATEWAY_API,
                description="Wait for Gateway API CRDs",
                timeout=300
            )
        ]
    
    def validation_scripts(self) -> List[ScriptReference]:
        """Return verification scripts"""
        return [
            ScriptReference(
                package="workflow_engine.adapters.cilium.scripts",
                resource=CiliumScripts.VALIDATE_CNI,
                description="Verify pod networking",
                timeout=60
            )
        ]
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate Cilium manifests and capability data"""
        config = CiliumConfig(**self.config)
        
        # Get ArgoCD repo URL from cross-adapter config
        repo_url = self.get_cross_adapter_config('argocd', 'control_plane_repo_url')
        
        # Load environment-specific overlay config
        env = self._get_environment()
        overlay_config = self._load_overlay_config(env)
        operator_replicas = overlay_config.get('cilium', {}).get('operator_replicas', 2)
        
        # Get Envoy and Cilium images from VersionProvider (no fallbacks)
        envoy_image = self._get_version_config('cilium', 'default_envoy_image')
        cilium_image = self._get_version_config('cilium', 'default_cilium_image')
        operator_image = self._get_version_config('cilium', 'default_operator_image')
        
        if not all([envoy_image, cilium_image, operator_image]):
            raise ValueError("Missing required Cilium image configuration in versions.yaml")
        
        # Load and render all modular templates in order
        template_files = [
            "bootstrap/01-crds.yaml.j2",
            "bootstrap/02-serviceaccounts.yaml.j2",
            "bootstrap/03-configmaps.yaml.j2",
            "bootstrap/04-envoy-config.yaml.j2",
            "bootstrap/05-rbac.yaml.j2",
            "bootstrap/06-rolebindings.yaml.j2",
            "bootstrap/07-agent-daemonset.yaml.j2",
            "bootstrap/08-envoy-daemonset.yaml.j2",
            "bootstrap/09-operator-deployment.yaml.j2"
        ]
        
        rendered_parts = []
        for template_file in template_files:
            template = self.jinja_env.get_template(f"cilium/{template_file}")
            rendered = await template.render_async(
                version=config.version,
                operator_replicas=operator_replicas,
                envoy_image=envoy_image,
                cilium_image=cilium_image,
                operator_image=operator_image
            )
            rendered_parts.append(rendered)
        
        # Concatenate all rendered templates with separator
        manifests_content = "\n---\n".join(rendered_parts)
        
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
        
        manifests = {}
        
        # 1. ArgoCD Application for Gateway API (wave 4)
        manifests["argocd/k8/core/04-gateway-config.yaml"] = self._render_gateway_argocd_app(repo_url)
        
        # 2. CNI manifests for Talos bootstrap embedding
        manifests["talos/templates/cilium/02-configmaps.yaml"] = manifests_content
        
        # 3. Network policies for foundation
        netpol_template = self.jinja_env.get_template("cilium/network-policies.yaml.j2")
        manifests["argocd/k8/foundation/network-policies/platform-egress.yaml"] = await netpol_template.render_async()
        
        return AdapterOutput(
            manifests=manifests,
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
    
    def _render_gateway_argocd_app(self, repo_url: str) -> str:
        """Generate ArgoCD Application for Gateway API"""
        app = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {
                "name": "gateway-foundation",
                "namespace": "argocd",
                "annotations": {
                    "argocd.argoproj.io/sync-wave": "4"
                }
            },
            "spec": {
                "project": "default",
                "source": {
                    "repoURL": repo_url,
                    "targetRevision": "main",
                    "path": "platform/generated/argocd/k8/core/gateway/gateway-foundation"
                },
                "destination": {
                    "server": "https://kubernetes.default.svc",
                    "namespace": "default"
                },
                "syncPolicy": {
                    "automated": {
                        "prune": True,
                        "selfHeal": True
                    },
                    "syncOptions": ["ServerSideApply=true"]
                }
            }
        }
        return yaml.dump(app, sort_keys=False)
    
    def _get_environment(self) -> str:
        """Get current environment from platform config or context"""
        # Try to get from platform.yaml
        platform_yaml = Path("platform/platform.yaml")
        if platform_yaml.exists():
            with open(platform_yaml) as f:
                platform_data = yaml.safe_load(f)
                mode = platform_data.get('platform', {}).get('mode', 'dev')
                return mode
        return 'dev'
    
    def _load_overlay_config(self, env: str) -> Dict[str, Any]:
        """Load environment-specific overlay configuration"""
        overlay_path = Path(__file__).parent.parent.parent / f"templates/overlays/{env}/configs.yaml"
        if overlay_path.exists():
            with open(overlay_path) as f:
                return yaml.safe_load(f) or {}
        return {}
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata"""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        if not metadata_path.exists():
            return {
                "name": "cilium",
                "version": "1.0.0",
                "phase": "networking",
                "selection_group": "network_tool",
                "group_order": 5,
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

    def get_stage_context(self, stage_name: str, all_adapters_config: Dict[str, Any]) -> Dict[str, Any]:
        """Return non-sensitive context for Cilium bootstrap stages"""
        return {
            'version': self.config['version'],
            'bgp_enabled': self.config.get('bgp', {}).get('enabled'),
            'bgp_asn': self.config.get('bgp', {}).get('asn'),
        }
