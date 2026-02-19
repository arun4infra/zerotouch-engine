"""ArgoCD adapter for GitOps platform management"""

from enum import Enum
from typing import List, Type, Dict, Any
from pathlib import Path
from pydantic import BaseModel
import yaml
from workflow_engine.adapters.base import PlatformAdapter, InputPrompt, ScriptReference, AdapterOutput
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


class ArgocdAdapter(PlatformAdapter):
    """ArgoCD GitOps platform adapter"""
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata from ArgoCD adapter directory"""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        return yaml.safe_load(metadata_path.read_text())
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return ArgoCDConfig
    
    def init(self) -> List[ScriptReference]:
        """ArgoCD adapter has no init scripts"""
        return []
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Interactive prompts for ztc init"""
        return [
            InputPrompt(
                name="version",
                prompt="ArgoCD Version",
                type="string",
                default="v3.2.0",
                help_text="ArgoCD version to install"
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
                prompt="Platform Repository URL (with .git suffix)",
                type="string",
                validation=r"^https://github\.com/.+\.git$",
                help_text="Git repository URL for platform manifests"
            ),
            InputPrompt(
                name="platform_repo_branch",
                prompt="Platform Repository Branch",
                type="string",
                default="main",
                help_text="Git branch to track"
            ),
            InputPrompt(
                name="overlay_environment",
                prompt="Overlay Environment",
                type="choice",
                choices=["main", "preview", "dev"],
                default="main",
                help_text="Kustomize overlay environment"
            ),
            InputPrompt(
                name="admin_password",
                prompt="Admin Password",
                type="password",
                help_text="ArgoCD admin password (min 8 characters)"
            ),
            InputPrompt(
                name="mode",
                prompt="Deployment Mode",
                type="choice",
                choices=["production", "preview"],
                default="production",
                help_text="ArgoCD deployment mode"
            )
        ]
    
    def derive_field_value(self, field_name: str, current_config: Dict[str, Any]) -> Any:
        """Derive values from other adapters"""
        # Get platform_repo_url from GitHub adapter
        if field_name == "platform_repo_url":
            github_url = self.get_cross_adapter_config("github", "control_plane_repo_url")
            if github_url:
                # Add .git suffix if not present
                if not github_url.endswith(".git"):
                    return f"{github_url}.git"
                return github_url
        
        # Auto-generate admin_password
        if field_name == "admin_password":
            import secrets
            import string
            # Generate 16-character password with letters, digits, and special chars
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            password = ''.join(secrets.choice(alphabet) for _ in range(16))
            return password
        
        return None
    
    def pre_work_scripts(self) -> List[ScriptReference]:
        """Pre-work scripts (CLI installation)"""
        config = ArgoCDConfig(**self.config)
        
        return [
            ScriptReference(
                package="workflow_engine.adapters.argocd.scripts",
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
                package="workflow_engine.adapters.argocd.scripts",
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
                package="workflow_engine.adapters.argocd.scripts",
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
                package="workflow_engine.adapters.argocd.scripts",
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
                package="workflow_engine.adapters.argocd.scripts",
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
                package="workflow_engine.adapters.argocd.scripts",
                resource=ArgoCDScripts.VALIDATE_HEALTH,
                description="Validate ArgoCD health",
                timeout=60,
                context_data={
                    "namespace": config.namespace
                }
            ),
            ScriptReference(
                package="workflow_engine.adapters.argocd.scripts",
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
            # Production mode: generate at argocd/install/
            kustomization_template = self.jinja_env.get_template("argocd/kustomization-production.yaml.j2")
            manifests["argocd/install/kustomization.yaml"] = await kustomization_template.render_async(**template_ctx)
            
            # Render patches at argocd/install/ level
            cm_patch_template = self.jinja_env.get_template("argocd/argocd-cm-patch.yaml.j2")
            manifests["argocd/install/argocd-cm-patch.yaml"] = await cm_patch_template.render_async(**template_ctx)
            
            app_controller_netpol_template = self.jinja_env.get_template("argocd/argocd-application-controller-netpol-patch.yaml.j2")
            manifests["argocd/install/argocd-application-controller-netpol-patch.yaml"] = await app_controller_netpol_template.render_async(**template_ctx)
            
            repo_server_netpol_template = self.jinja_env.get_template("argocd/argocd-repo-server-netpol-patch.yaml.j2")
            manifests["argocd/install/argocd-repo-server-netpol-patch.yaml"] = await repo_server_netpol_template.render_async(**template_ctx)
            
            ksops_init_template = self.jinja_env.get_template("argocd/repo-server-ksops-init.yaml.j2")
            manifests["argocd/install/repo-server-ksops-init.yaml"] = await ksops_init_template.render_async(**template_ctx)
        else:
            # Preview mode: generate at argocd/install/preview/
            kustomization_template = self.jinja_env.get_template("argocd/kustomization-preview.yaml.j2")
            manifests["argocd/install/preview/kustomization.yaml"] = await kustomization_template.render_async(**template_ctx)
            
            # Render patches at argocd/install/preview/ level (duplicates for Kustomize path resolution)
            cm_patch_template = self.jinja_env.get_template("argocd/argocd-cm-patch.yaml.j2")
            manifests["argocd/install/preview/argocd-cm-patch.yaml"] = await cm_patch_template.render_async(**template_ctx)
            
            app_controller_netpol_template = self.jinja_env.get_template("argocd/argocd-application-controller-netpol-patch.yaml.j2")
            manifests["argocd/install/preview/argocd-application-controller-netpol-patch.yaml"] = await app_controller_netpol_template.render_async(**template_ctx)
            
            repo_server_netpol_template = self.jinja_env.get_template("argocd/argocd-repo-server-netpol-patch.yaml.j2")
            manifests["argocd/install/preview/argocd-repo-server-netpol-patch.yaml"] = await repo_server_netpol_template.render_async(**template_ctx)
            
            ksops_init_template = self.jinja_env.get_template("argocd/repo-server-ksops-init.yaml.j2")
            manifests["argocd/install/preview/repo-server-ksops-init.yaml"] = await ksops_init_template.render_async(**template_ctx)
            
            # Preview-specific: repo mount patch
            repo_mount_template = self.jinja_env.get_template("argocd/repo-mount-patch.yaml.j2")
            manifests["argocd/install/preview/repo-mount-patch.yaml"] = await repo_mount_template.render_async(**template_ctx)
        
        # Render bootstrap configuration (shared)
        bootstrap_config_template = self.jinja_env.get_template("argocd/bootstrap-config.yaml.j2")
        manifests["argocd/bootstrap-files/config.yaml"] = await bootstrap_config_template.render_async(**template_ctx)
        
        # Render admin patch (shared)
        admin_patch_template = self.jinja_env.get_template("argocd/argocd-admin-patch.yaml.j2")
        manifests["argocd/bootstrap-files/argocd-admin-patch.yaml"] = await admin_patch_template.render_async(**template_ctx)
        
        # Render overlay kustomizations (shared)
        overlay_main_template = self.jinja_env.get_template("argocd/overlay-main-kustomization.yaml.j2")
        manifests["argocd/k8/kustomization.yaml"] = await overlay_main_template.render_async(**template_ctx)
        
        overlay_preview_template = self.jinja_env.get_template("argocd/overlay-preview-kustomization.yaml.j2")
        manifests["argocd/kind/kustomization.yaml"] = await overlay_preview_template.render_async(**template_ctx)
        
        # Render root Application manifests (shared)
        overlay_main_root_template = self.jinja_env.get_template("argocd/overlay-main-root.yaml.j2")
        manifests["argocd/k8/root.yaml"] = await overlay_main_root_template.render_async(**template_ctx)
        
        overlay_preview_root_template = self.jinja_env.get_template("argocd/overlay-preview-root.yaml.j2")
        manifests["argocd/kind/root.yaml"] = await overlay_preview_root_template.render_async(**template_ctx)
        
        # Render foundation-config Application
        foundation_config_template = self.jinja_env.get_template("argocd/foundation-config-application.yaml.j2")
        manifests["argocd/base/03-foundation-config.yaml"] = await foundation_config_template.render_async(**template_ctx)
        
        # Get tenant repo URL from GitHub adapter
        tenant_repo_url = self.get_cross_adapter_config("github", "data_plane_repo_url") or ""
        
        # Render tenant-infrastructure Application
        tenant_infra_template = self.jinja_env.get_template("argocd/tenant-infrastructure-application.yaml.j2")
        manifests["argocd/k8/core/tenant-infrastructure.yaml"] = await tenant_infra_template.render_async(
            tenant_repo_url=tenant_repo_url
        )
        
        # Create empty core/ directories (placeholders for other adapters)
        manifests["argocd/k8/core/.gitkeep"] = ""
        manifests["argocd/kind/core/.gitkeep"] = ""
        
        # Create empty environment directories (dev, staging, prod)
        manifests["argocd/k8/overlays/dev/.gitkeep"] = ""
        manifests["argocd/k8/overlays/staging/.gitkeep"] = ""
        manifests["argocd/k8/overlays/prod/.gitkeep"] = ""
        
        # GitOps platform capability data (empty - gitops-platform not a registered capability)
        capability_data = {}
        
        return AdapterOutput(
            manifests=manifests,
            stages=[],
            env_vars={},
            capabilities=capability_data,
            data={
                "repo_url": config.platform_repo_url,
                "target_revision": config.platform_repo_branch
            }
        )
