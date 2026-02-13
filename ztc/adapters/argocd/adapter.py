"""ArgoCD adapter for GitOps platform management"""

from enum import Enum
from typing import List, Type, Dict, Any
from pathlib import Path
from pydantic import BaseModel
import yaml
from ztc.adapters.base import PlatformAdapter, InputPrompt, ScriptReference, AdapterOutput
from .config import ArgoCDConfig


class ArgoCDScripts(str, Enum):
    """Script resource paths (validated at class load)"""
    # Pre-work (1 script)
    INSTALL_CLI = "pre_work/install-argocd-cli.sh"
    
    # Bootstrap (2 scripts)
    INSTALL_ARGOCD = "bootstrap/install-argocd.sh"
    PATCH_ADMIN_PASSWORD = "bootstrap/patch-admin-password.sh"
    
    # Post-work (2 scripts)
    WAIT_PODS = "post_work/wait-argocd-pods.sh"
    WAIT_REPO_SERVER = "post_work/wait-repo-server.sh"
    
    # Validation (2 scripts)
    VALIDATE_HEALTH = "validation/validate-argocd-health.sh"
    VALIDATE_KSOPS = "validation/validate-ksops-integration.sh"


class ArgoCDAdapter(PlatformAdapter):
    """ArgoCD GitOps platform adapter"""
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata from ArgoCD adapter directory"""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        return yaml.safe_load(metadata_path.read_text())
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return ArgoCDConfig
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Interactive prompts for ztc init"""
        return [
            InputPrompt(
                name="version",
                prompt="ArgoCD Version",
                type="string",
                default="v3.2.0",
                help_text="ArgoCD version to install (e.g., v3.2.0)"
            ),
            InputPrompt(
                name="namespace",
                prompt="Namespace",
                type="string",
                default="argocd",
                help_text="Kubernetes namespace for ArgoCD"
            ),
            InputPrompt(
                name="platform_repo_url",
                prompt="Platform Repository URL",
                type="string",
                help_text="Git repository URL for platform manifests (e.g., https://github.com/org/repo.git)"
            ),
            InputPrompt(
                name="platform_repo_branch",
                prompt="Platform Repository Branch",
                type="string",
                default="main",
                help_text="Git branch or tag to sync"
            ),
            InputPrompt(
                name="overlay_environment",
                prompt="Overlay Environment",
                type="choice",
                choices=["main", "preview", "dev"],
                default="main",
                help_text="Environment overlay to use"
            ),
            InputPrompt(
                name="admin_password",
                prompt="Admin Password",
                type="password",
                help_text="ArgoCD admin user password (min 8 characters)"
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
        """Pre-work scripts (CLI installation)"""
        config = ArgoCDConfig(**self.config)
        
        return [
            ScriptReference(
                package="ztc.adapters.argocd.scripts",
                resource=ArgoCDScripts.INSTALL_CLI,
                description="Install ArgoCD CLI",
                timeout=120,
                context_data={
                    "argocd_version": config.version,
                    "install_path": "/usr/local/bin/argocd"
                }
            )
        ]
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """Core ArgoCD installation scripts"""
        config = ArgoCDConfig(**self.config)
        
        manifests_path = f"platform/generated/argocd/install"
        if config.mode == "preview":
            manifests_path = f"{manifests_path}/preview"
        
        return [
            ScriptReference(
                package="ztc.adapters.argocd.scripts",
                resource=ArgoCDScripts.INSTALL_ARGOCD,
                description="Install ArgoCD to cluster",
                timeout=300,
                context_data={
                    "namespace": config.namespace,
                    "mode": config.mode,
                    "manifests_path": manifests_path
                }
            ),
            ScriptReference(
                package="ztc.adapters.argocd.scripts",
                resource=ArgoCDScripts.PATCH_ADMIN_PASSWORD,
                description="Configure admin password",
                timeout=60,
                context_data={
                    "namespace": config.namespace
                },
                secret_env_vars={
                    "ADMIN_PASSWORD": config.admin_password.get_secret_value()
                }
            )
        ]
    
    def post_work_scripts(self) -> List[ScriptReference]:
        """Wait for ArgoCD readiness"""
        config = ArgoCDConfig(**self.config)
        
        return [
            ScriptReference(
                package="ztc.adapters.argocd.scripts",
                resource=ArgoCDScripts.WAIT_PODS,
                description="Wait for ArgoCD pods",
                timeout=300,
                context_data={
                    "namespace": config.namespace,
                    "timeout_seconds": 300,
                    "check_interval": 5
                }
            ),
            ScriptReference(
                package="ztc.adapters.argocd.scripts",
                resource=ArgoCDScripts.WAIT_REPO_SERVER,
                description="Wait for repo server",
                timeout=120,
                context_data={
                    "namespace": config.namespace,
                    "timeout_seconds": 120,
                    "check_interval": 3
                }
            )
        ]
    
    def validation_scripts(self) -> List[ScriptReference]:
        """ArgoCD deployment validation"""
        config = ArgoCDConfig(**self.config)
        
        return [
            ScriptReference(
                package="ztc.adapters.argocd.scripts",
                resource=ArgoCDScripts.VALIDATE_HEALTH,
                description="Validate ArgoCD health",
                timeout=60,
                context_data={
                    "namespace": config.namespace
                }
            ),
            ScriptReference(
                package="ztc.adapters.argocd.scripts",
                resource=ArgoCDScripts.VALIDATE_KSOPS,
                description="Validate KSOPS integration",
                timeout=60,
                context_data={
                    "namespace": config.namespace
                }
            )
        ]
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate ArgoCD installation manifests and bootstrap configuration"""
        config = ArgoCDConfig(**self.config)
        
        manifests = {}
        
        # Template context
        template_ctx = {
            "version": config.version,
            "namespace": config.namespace,
            "repo_url": config.platform_repo_url,
            "target_revision": config.platform_repo_branch,
            "overlay_environment": config.overlay_environment,
            "mode": config.mode
        }
        
        # Render production or preview kustomization
        if config.mode == "production":
            kustomization_template = self.jinja_env.get_template("argocd/kustomization-production.yaml.j2")
            manifests["install/kustomization.yaml"] = await kustomization_template.render_async(**template_ctx)
        else:
            kustomization_template = self.jinja_env.get_template("argocd/kustomization-preview.yaml.j2")
            manifests["install/preview/kustomization.yaml"] = await kustomization_template.render_async(**template_ctx)
        
        # Render ConfigMap patch
        cm_patch_template = self.jinja_env.get_template("argocd/argocd-cm-patch.yaml.j2")
        manifests["install/argocd-cm-patch.yaml"] = await cm_patch_template.render_async(**template_ctx)
        
        # Render NetworkPolicy patches
        app_controller_netpol_template = self.jinja_env.get_template("argocd/argocd-application-controller-netpol-patch.yaml.j2")
        manifests["install/argocd-application-controller-netpol-patch.yaml"] = await app_controller_netpol_template.render_async(**template_ctx)
        
        repo_server_netpol_template = self.jinja_env.get_template("argocd/argocd-repo-server-netpol-patch.yaml.j2")
        manifests["install/argocd-repo-server-netpol-patch.yaml"] = await repo_server_netpol_template.render_async(**template_ctx)
        
        # Render KSOPS init container patch
        ksops_init_template = self.jinja_env.get_template("argocd/repo-server-ksops-init.yaml.j2")
        manifests["install/repo-server-ksops-init.yaml"] = await ksops_init_template.render_async(**template_ctx)
        
        # Render bootstrap configuration
        bootstrap_config_template = self.jinja_env.get_template("argocd/bootstrap-config.yaml.j2")
        manifests["bootstrap-files/config.yaml"] = await bootstrap_config_template.render_async(**template_ctx)
        
        # Render overlay kustomizations
        overlay_main_template = self.jinja_env.get_template("argocd/overlay-main-kustomization.yaml.j2")
        manifests["overlays/main/kustomization.yaml"] = await overlay_main_template.render_async(**template_ctx)
        
        overlay_preview_template = self.jinja_env.get_template("argocd/overlay-preview-kustomization.yaml.j2")
        manifests["overlays/preview/kustomization.yaml"] = await overlay_preview_template.render_async(**template_ctx)
        
        # GitOps platform capability data
        capability_data = {
            "gitops-platform": {
                "argocd_endpoint": f"https://argocd.{config.namespace}.svc.cluster.local",
                "admin_username": "admin",
                "admin_password": config.admin_password.get_secret_value(),
                "namespace": config.namespace,
                "version": config.version
            }
        }
        
        return AdapterOutput(
            manifests=manifests,
            stages=[],
            env_vars={},
            capabilities=capability_data,
            data={}
        )
