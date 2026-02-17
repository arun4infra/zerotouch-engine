"""Crossplane adapter implementation."""

from enum import Enum
from typing import List, Type, Dict, Any
from pathlib import Path
from pydantic import BaseModel
import yaml

from ztc.adapters.base import PlatformAdapter, InputPrompt, ScriptReference, AdapterOutput
from ztc.adapters.crossplane.config import CrossplaneConfig


class CrossplaneScripts(str, Enum):
    """Script resource paths (validated at class load)"""
    # Pre-work (1 script)
    INSTALL_CLI = "pre_work/install-crossplane-cli.sh"
    
    # Bootstrap (none - ArgoCD handles deployment)
    
    # Post-work (2 scripts)
    WAIT_OPERATOR = "post_work/wait-operator-ready.sh"
    WAIT_CRDS = "post_work/wait-provider-crds.sh"
    
    # Validation (2 scripts)
    VALIDATE_HEALTH = "validation/validate-operator-health.sh"
    VALIDATE_PROVIDERS = "validation/validate-providers.sh"


class CrossplaneAdapter(PlatformAdapter):
    """Crossplane adapter for infrastructure provisioning."""

    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata from Crossplane adapter directory."""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        return yaml.safe_load(metadata_path.read_text())

    @property
    def config_model(self) -> Type[BaseModel]:
        """Return Pydantic model for config validation."""
        return CrossplaneConfig

    def init(self) -> List[ScriptReference]:
        """Crossplane adapter has no init scripts"""
        return []
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Return list of interactive prompts for user input collection."""
        return [
            InputPrompt(
                name="version",
                prompt="Crossplane Version",
                type="string",
                default="1.16.0",
                help_text="Crossplane Helm chart version (e.g., 1.16.0)"
            ),
            InputPrompt(
                name="namespace",
                prompt="Namespace",
                type="string",
                default="crossplane-system",
                help_text="Kubernetes namespace for Crossplane"
            ),
            InputPrompt(
                name="enable_composition_revisions",
                prompt="Enable Composition Revisions",
                type="boolean",
                default=True,
                help_text="Enable composition revisions feature"
            ),
            InputPrompt(
                name="mode",
                prompt="Deployment Mode",
                type="choice",
                choices=["production", "preview"],
                default="production",
                help_text="Production (Talos) or Preview (Kind)"
            ),
            InputPrompt(
                name="providers",
                prompt="Providers",
                type="string",
                default="kubernetes",
                help_text="Comma-separated list of providers (kubernetes,aws,hetzner)"
            )
        ]
    
    def derive_field_value(self, field_name: str, current_config: Dict[str, Any]) -> Any:
        """Convert providers string to list format"""
        if field_name == "providers":
            # If providers comes from default or env var as string, convert to list
            # This handles: "kubernetes" -> ["kubernetes"] or "kubernetes,aws" -> ["kubernetes", "aws"]
            providers_value = current_config.get("providers")
            if isinstance(providers_value, str):
                # Split by comma and strip whitespace
                return [p.strip() for p in providers_value.split(",")]
        return None

    def pre_work_scripts(self) -> List[ScriptReference]:
        """Return pre-work scripts."""
        config = CrossplaneConfig(**self.config)
        
        return [
            ScriptReference(
                package="ztc.adapters.crossplane.scripts",
                resource=CrossplaneScripts.INSTALL_CLI,
                description="Install kubectl-crossplane plugin",
                timeout=120,
                context_data={
                    "version": config.version,
                    "install_path": "/usr/local/bin/kubectl-crossplane"
                }
            )
        ]

    def bootstrap_scripts(self) -> List[ScriptReference]:
        """Return core adapter responsibility scripts."""
        # ArgoCD handles deployment
        return []

    def post_work_scripts(self) -> List[ScriptReference]:
        """Return post-work scripts."""
        config = CrossplaneConfig(**self.config)
        
        return [
            ScriptReference(
                package="ztc.adapters.crossplane.scripts",
                resource=CrossplaneScripts.WAIT_OPERATOR,
                description="Wait for Crossplane operator",
                timeout=300,
                context_data={
                    "namespace": config.namespace,
                    "timeout_seconds": 300,
                    "check_interval": 5
                }
            ),
            ScriptReference(
                package="ztc.adapters.crossplane.scripts",
                resource=CrossplaneScripts.WAIT_CRDS,
                description="Wait for provider CRDs",
                timeout=180,
                context_data={
                    "namespace": config.namespace,
                    "timeout_seconds": 180,
                    "check_interval": 3,
                    "required_crds": [
                        "providers.pkg.crossplane.io",
                        "providerconfigs.pkg.crossplane.io"
                    ]
                }
            )
        ]

    def validation_scripts(self) -> List[ScriptReference]:
        """Return verification scripts."""
        config = CrossplaneConfig(**self.config)
        
        return [
            ScriptReference(
                package="ztc.adapters.crossplane.scripts",
                resource=CrossplaneScripts.VALIDATE_HEALTH,
                description="Validate Crossplane operator health",
                timeout=60,
                context_data={
                    "namespace": config.namespace
                }
            ),
            ScriptReference(
                package="ztc.adapters.crossplane.scripts",
                resource=CrossplaneScripts.VALIDATE_PROVIDERS,
                description="Validate provider installations",
                timeout=60,
                context_data={
                    "namespace": config.namespace,
                    "expected_providers": config.providers
                }
            )
        ]

    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate manifests, configs, and stage definitions."""
        config = CrossplaneConfig(**self.config)
        
        manifests = {}
        
        # Template context
        template_ctx = {
            "version": config.version,
            "namespace": config.namespace,
            "enable_composition_revisions": config.enable_composition_revisions,
            "mode": config.mode,
            "providers": config.providers
        }
        
        # Render core operator Application to ArgoCD overlay
        core_template = self.jinja_env.get_template("crossplane/core/application.yaml.j2")
        manifests["argocd/overlays/main/core/01-crossplane.yaml"] = await core_template.render_async(**template_ctx)
        
        # Render provider manifests to foundation directory
        for provider in config.providers:
            provider_template = self.jinja_env.get_template(f"crossplane/providers/{provider}.yaml.j2")
            manifests[f"argocd/overlays/main/foundation/provider-{provider}.yaml"] = await provider_template.render_async(**template_ctx)
        
        # Import capability model
        from ztc.interfaces.capabilities import InfrastructureProvisioningCapability
        
        # Infrastructure provisioning capability data
        capability_data = {
            "infrastructure-provisioning": InfrastructureProvisioningCapability(
                operator_version=config.version,
                namespace=config.namespace,
                installed_providers=config.providers,
                crds_ready=False
            )
        }
        
        return AdapterOutput(
            manifests=manifests,
            stages=[],
            env_vars={},
            capabilities=capability_data,
            data={}
        )
