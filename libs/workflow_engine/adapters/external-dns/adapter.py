"""External-DNS adapter for DNS management"""

from enum import Enum
from typing import List, Type, Dict, Any
from pathlib import Path
from pydantic import BaseModel
import yaml
from workflow_engine.adapters.base import PlatformAdapter, InputPrompt, ScriptReference, AdapterOutput
from .config import ExternalDNSConfig


class ExternalDNSScripts(str, Enum):
    """Script resource paths"""
    # Post-work (1 script)
    WAIT_EXTERNAL_DNS = "post_work/wait-external-dns.sh"
    
    # Validation (1 script)
    VALIDATE_EXTERNAL_DNS = "validation/validate-external-dns.sh"


class ExternalDnsAdapter(PlatformAdapter):
    """External-DNS adapter with dynamic provider selection"""
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata"""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        return yaml.safe_load(metadata_path.read_text())
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return ExternalDNSConfig
    
    def init(self) -> List[ScriptReference]:
        """External-DNS adapter has no init scripts"""
        return []
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Interactive prompts for ztc init"""
        return [
            InputPrompt(
                name="version",
                prompt="External-DNS Version",
                type="string",
                default="1.15.0",
                help_text="External-DNS Helm chart version to install (e.g., 1.15.0)"
            ),
            InputPrompt(
                name="namespace",
                prompt="Namespace",
                type="string",
                default="external-dns",
                help_text="Kubernetes namespace for External-DNS"
            ),
            InputPrompt(
                name="provider",
                prompt="DNS Provider",
                type="choice",
                choices=["hetzner", "aws"],
                default="hetzner",
                help_text="DNS provider (Hetzner or AWS Route53)"
            ),
            InputPrompt(
                name="mode",
                prompt="Deployment Mode",
                type="choice",
                choices=["production", "preview"],
                default="production",
                help_text="Production (Talos) or Preview (Kind)"
            )
        ]
    
    def pre_work_scripts(self) -> List[ScriptReference]:
        """No pre-work scripts"""
        return []
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """No bootstrap scripts - ArgoCD handles deployment"""
        return []
    
    def post_work_scripts(self) -> List[ScriptReference]:
        """Wait for External-DNS readiness"""
        config = ExternalDNSConfig(**self.config)
        
        return [
            ScriptReference(
                package="workflow_engine.adapters.external-dns.scripts",
                resource=ExternalDNSScripts.WAIT_EXTERNAL_DNS,
                description="Wait for External-DNS deployment",
                timeout=300,
                context_data={
                    "namespace": config.namespace,
                    "timeout_seconds": 300,
                    "check_interval": 5
                }
            )
        ]
    
    def validation_scripts(self) -> List[ScriptReference]:
        """External-DNS deployment validation"""
        config = ExternalDNSConfig(**self.config)
        
        return [
            ScriptReference(
                package="workflow_engine.adapters.external-dns.scripts",
                resource=ExternalDNSScripts.VALIDATE_EXTERNAL_DNS,
                description="Validate External-DNS health",
                timeout=60,
                context_data={
                    "namespace": config.namespace
                }
            )
        ]
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate External-DNS ArgoCD Application manifest with dynamic provider selection"""
        config = ExternalDNSConfig(**self.config)
        
        # Get provider from cloud-infrastructure capability if available
        provider = config.provider
        try:
            cloud_cap = ctx.get_capability_data('cloud-infrastructure')
            if cloud_cap and hasattr(cloud_cap, 'provider'):
                provider = cloud_cap.provider
        except Exception:
            # Use config provider if capability not available
            pass
        
        manifests = {}
        
        # Template context
        template_ctx = {
            "version": config.version,
            "namespace": config.namespace,
            "provider": provider,
            "mode": config.mode
        }
        
        # Render ArgoCD Application
        app_template = self.jinja_env.get_template("external-dns/application.yaml.j2")
        manifests["argocd/overlays/main/core/01-external-dns.yaml"] = await app_template.render_async(**template_ctx)
        
        # DNS capability data (empty - not a registered capability yet)
        capability_data = {}
        
        return AdapterOutput(
            manifests=manifests,
            stages=[],
            env_vars={},
            capabilities=capability_data,
            data={"provider": provider}
        )
