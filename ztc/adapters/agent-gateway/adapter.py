"""Agent Gateway adapter for platform routing and authentication"""

from enum import Enum
from typing import List, Type, Dict, Any
from pathlib import Path
from pydantic import BaseModel
import yaml
from ztc.adapters.base import PlatformAdapter, InputPrompt, ScriptReference, AdapterOutput
from .config import AgentGatewayConfig


class AgentGatewayScripts(str, Enum):
    """Script resource paths (validated at class load)"""
    # Validation (2 Python scripts)
    VALIDATE_GATEWAY_CONFIG = "validation/validate-gateway-config.py"
    VALIDATE_PLATFORM_AUTH = "validation/validate-platform-auth.py"


class AgentGatewayAdapter(PlatformAdapter):
    """Agent Gateway routing and authentication adapter"""
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata from Agent Gateway adapter directory"""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        return yaml.safe_load(metadata_path.read_text())
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return AgentGatewayConfig
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Interactive prompts for ztc init"""
        return [
            InputPrompt(
                name="image_tag",
                prompt="Image Tag",
                type="string",
                default="latest",
                help_text="Image tag for agent-gateway service"
            ),
            InputPrompt(
                name="namespace",
                prompt="Namespace",
                type="string",
                default="platform-agent-gateway",
                help_text="Kubernetes namespace for agent-gateway"
            ),
            InputPrompt(
                name="domain",
                prompt="Domain",
                type="string",
                default="agentgateway.nutgraf.in",
                help_text="Domain for agent-gateway routing"
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
        """Pre-work scripts (none for agent-gateway)"""
        return []
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """Core bootstrap scripts (none - ArgoCD handles deployment)"""
        return []
    
    def post_work_scripts(self) -> List[ScriptReference]:
        """Post-work scripts (none for agent-gateway)"""
        return []
    
    def validation_scripts(self) -> List[ScriptReference]:
        """Agent Gateway validation scripts"""
        config = AgentGatewayConfig(**self.config)
        
        return [
            ScriptReference(
                package="ztc.adapters.agent-gateway.scripts",
                resource=AgentGatewayScripts.VALIDATE_GATEWAY_CONFIG,
                description="Validate gateway configuration",
                timeout=120,
                context_data={
                    "gateway_host": config.domain,
                    "identity_host": "identity.nutgraf.in"
                }
            ),
            ScriptReference(
                package="ztc.adapters.agent-gateway.scripts",
                resource=AgentGatewayScripts.VALIDATE_PLATFORM_AUTH,
                description="Validate platform authentication flow",
                timeout=180,
                context_data={
                    "gateway_host": config.domain,
                    "identity_host": "identity.nutgraf.in",
                    "environment": config.mode
                }
            )
        ]
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate Agent Gateway manifests"""
        config = AgentGatewayConfig(**self.config)
        
        manifests = {}
        
        # Template context
        template_ctx = {
            "image_tag": config.image_tag,
            "namespace": config.namespace,
            "domain": config.domain,
            "mode": config.mode,
            "platform_repo_url": "https://github.com/arun4infra/zerotouch-platform.git",
            "platform_repo_branch": "main"
        }
        
        # Render application manifest
        app_template = self.jinja_env.get_template("agent-gateway/application.yaml.j2")
        manifests["argocd/base/06-agentgateway.yaml"] = await app_template.render_async(**template_ctx)
        
        # Render agentgateway manifests
        configmap_template = self.jinja_env.get_template("agent-gateway/manifests/configmap.yaml.j2")
        manifests["argocd/overlays/main/core/agentgateway/configmap.yaml"] = await configmap_template.render_async(**template_ctx)
        
        deployment_template = self.jinja_env.get_template("agent-gateway/manifests/deployment.yaml.j2")
        manifests["argocd/overlays/main/core/agentgateway/deployment.yaml"] = await deployment_template.render_async(**template_ctx)
        
        service_template = self.jinja_env.get_template("agent-gateway/manifests/service.yaml.j2")
        manifests["argocd/overlays/main/core/agentgateway/service.yaml"] = await service_template.render_async(**template_ctx)
        
        kustomization_template = self.jinja_env.get_template("agent-gateway/manifests/kustomization.yaml.j2")
        manifests["argocd/overlays/main/core/agentgateway/kustomization.yaml"] = await kustomization_template.render_async(**template_ctx)
        
        # Render HTTPRoute
        httproute_template = self.jinja_env.get_template("agent-gateway/httproute/httproute.yaml.j2")
        manifests["argocd/overlays/main/core/agentgateway-httproute/httproute.yaml"] = await httproute_template.render_async(**template_ctx)
        
        httproute_kustomization_template = self.jinja_env.get_template("agent-gateway/httproute/kustomization.yaml.j2")
        manifests["argocd/overlays/main/core/agentgateway-httproute/kustomization.yaml"] = await httproute_kustomization_template.render_async(**template_ctx)
        
        # Agent gateway capability data (empty for now)
        capability_data = {}
        
        return AdapterOutput(
            manifests=manifests,
            stages=[],
            env_vars={},
            capabilities=capability_data,
            data={}
        )
