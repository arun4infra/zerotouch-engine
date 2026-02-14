"""Gateway API adapter for middleware infrastructure"""

from enum import Enum
from typing import List, Type, Dict, Any
from pathlib import Path
from pydantic import BaseModel
import yaml
from ztc.adapters.base import PlatformAdapter, InputPrompt, ScriptReference, AdapterOutput
from .config import GatewayAPIConfig


class GatewayAPIScripts(str, Enum):
    """Script resource paths (validated at class load)"""
    # Post-work (2 scripts)
    WAIT_GATEWAY_API = "post_work/wait-gateway-api.sh"
    WAIT_GATEWAY = "post_work/wait-gateway-lb.sh"
    
    # Validation (1 script)
    VALIDATE_GATEWAY_CONFIG = "validation/validate-gateway-config.sh"


class GatewayAPIAdapter(PlatformAdapter):
    """Gateway API infrastructure adapter"""
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata from Gateway API adapter directory"""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        return yaml.safe_load(metadata_path.read_text())
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return GatewayAPIConfig
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Interactive prompts for ztc init"""
        return [
            InputPrompt(
                name="gateway_api_version",
                prompt="Gateway API Version",
                type="string",
                default="v1.4.1",
                help_text="Gateway API version to install (e.g., v1.4.1)"
            ),
            InputPrompt(
                name="domain",
                prompt="Platform Domain",
                type="string",
                default="nutgraf.in",
                help_text="Platform domain for certificates and routing"
            ),
            InputPrompt(
                name="email",
                prompt="Certificate Email",
                type="string",
                default="admin@nutgraf.in",
                help_text="Email for Let's Encrypt certificate notifications"
            ),
            InputPrompt(
                name="hetzner_location",
                prompt="Hetzner Location",
                type="string",
                default="fsn1",
                help_text="Hetzner datacenter location for load balancer"
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
        """Pre-work scripts (none for gateway-api)"""
        return []
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """Core bootstrap scripts (none - ArgoCD handles deployment)"""
        return []
    
    def post_work_scripts(self) -> List[ScriptReference]:
        """Wait for Gateway API readiness"""
        config = GatewayAPIConfig(**self.config)
        
        return [
            ScriptReference(
                package="ztc.adapters.gateway-api.scripts",
                resource=GatewayAPIScripts.WAIT_GATEWAY_API,
                description="Wait for Gateway API CRDs and Cilium sync",
                timeout=300,
                context_data={
                    "timeout_seconds": 300,
                    "check_interval": 5
                }
            ),
            ScriptReference(
                package="ztc.adapters.gateway-api.scripts",
                resource=GatewayAPIScripts.WAIT_GATEWAY,
                description="Wait for Gateway LoadBalancer IP",
                timeout=300,
                context_data={
                    "gateway_name": "public-gateway",
                    "namespace": "kube-system",
                    "timeout_seconds": 300
                }
            )
        ]
    
    def validation_scripts(self) -> List[ScriptReference]:
        """Gateway API deployment validation"""
        config = GatewayAPIConfig(**self.config)
        
        return [
            ScriptReference(
                package="ztc.adapters.gateway-api.scripts",
                resource=GatewayAPIScripts.VALIDATE_GATEWAY_CONFIG,
                description="Validate Gateway API configuration",
                timeout=60,
                context_data={
                    "gateway_name": "public-gateway",
                    "gateway_namespace": "kube-system",
                    "gatewayclass_name": "cilium"
                }
            )
        ]
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate Gateway API manifests"""
        config = GatewayAPIConfig(**self.config)
        
        manifests = {}
        
        # Get platform repo info from context (provided by argocd adapter)
        platform_repo_url = ctx.get("platform_repo_url", "https://github.com/arun4infra/zerotouch-platform.git")
        platform_repo_branch = ctx.get("platform_repo_branch", "main")
        
        # Template context
        template_ctx = {
            "gateway_api_version": config.gateway_api_version,
            "domain": config.domain,
            "email": config.email,
            "hetzner_location": config.hetzner_location,
            "mode": config.mode,
            "platform_repo_url": platform_repo_url,
            "platform_repo_branch": platform_repo_branch
        }
        
        # Render CRD application
        crds_template = self.jinja_env.get_template("crds/application.yaml.j2")
        manifests["argocd/base/00-gateway-api-crds.yaml"] = await crds_template.render_async(**template_ctx)
        
        # Render foundation manifests
        foundation_config_template = self.jinja_env.get_template("foundation/cilium-gateway-config.yaml.j2")
        manifests["argocd/overlays/main/core/gateway/gateway-foundation/cilium-gateway-config.yaml"] = await foundation_config_template.render_async(**template_ctx)
        
        foundation_rbac_template = self.jinja_env.get_template("foundation/cilium-gateway-rbac.yaml.j2")
        manifests["argocd/overlays/main/core/gateway/gateway-foundation/cilium-gateway-rbac.yaml"] = await foundation_rbac_template.render_async(**template_ctx)
        
        foundation_kustomization_template = self.jinja_env.get_template("foundation/kustomization.yaml.j2")
        manifests["argocd/overlays/main/core/gateway/gateway-foundation/kustomization.yaml"] = await foundation_kustomization_template.render_async(**template_ctx)
        
        # Render class manifests
        class_gatewayclass_template = self.jinja_env.get_template("class/cilium-gatewayclass.yaml.j2")
        manifests["argocd/overlays/main/core/gateway/gateway-class/cilium-gatewayclass.yaml"] = await class_gatewayclass_template.render_async(**template_ctx)
        
        class_kustomization_template = self.jinja_env.get_template("class/kustomization.yaml.j2")
        manifests["argocd/overlays/main/core/gateway/gateway-class/kustomization.yaml"] = await class_kustomization_template.render_async(**template_ctx)
        
        # Render config manifests
        config_bootstrap_issuer_template = self.jinja_env.get_template("config/bootstrap-issuer.yaml.j2")
        manifests["argocd/overlays/main/core/gateway/gateway-config/bootstrap-issuer.yaml"] = await config_bootstrap_issuer_template.render_async(**template_ctx)
        
        config_letsencrypt_issuer_template = self.jinja_env.get_template("config/letsencrypt-issuer.yaml.j2")
        manifests["argocd/overlays/main/core/gateway/gateway-config/letsencrypt-issuer.yaml"] = await config_letsencrypt_issuer_template.render_async(**template_ctx)
        
        config_certificate_template = self.jinja_env.get_template("config/gateway-certificate.yaml.j2")
        manifests["argocd/overlays/main/core/gateway/gateway-config/gateway-certificate.yaml"] = await config_certificate_template.render_async(**template_ctx)
        
        config_gateway_template = self.jinja_env.get_template("config/public-gateway.yaml.j2")
        manifests["argocd/overlays/main/core/gateway/gateway-config/public-gateway.yaml"] = await config_gateway_template.render_async(**template_ctx)
        
        config_kustomization_template = self.jinja_env.get_template("config/kustomization.yaml.j2")
        manifests["argocd/overlays/main/core/gateway/gateway-config/kustomization.yaml"] = await config_kustomization_template.render_async(**template_ctx)
        
        # Render parent application
        parent_app_template = self.jinja_env.get_template("parent-app.yaml.j2")
        manifests["argocd/overlays/main/core/04-gateway-config.yaml"] = await parent_app_template.render_async(**template_ctx)
        
        # Generate environment overlays (dev, staging, prod)
        for env in ["dev", "staging", "prod"]:
            env_template_ctx = {**template_ctx, "environment": env}
            # Environment-specific gateway configs can be added here if needed
            # For now, create placeholder .gitkeep files
            manifests[f"argocd/overlays/main/{env}/gateway/.gitkeep"] = ""
        
        # Gateway infrastructure capability data
        capability_data = {
            "gateway-infrastructure": {
                "gateway_name": "public-gateway",
                "gateway_namespace": "kube-system",
                "gatewayclass_name": "cilium",
                "load_balancer_ip": ""  # Populated during bootstrap
            }
        }
        
        return AdapterOutput(
            manifests=manifests,
            stages=[],
            env_vars={},
            capabilities=capability_data,
            data={}
        )
