"""Cert-manager adapter for certificate management"""

from enum import Enum
from typing import List, Type, Dict, Any
from pathlib import Path
from pydantic import BaseModel
import yaml
from workflow_engine.adapters.base import PlatformAdapter, InputPrompt, ScriptReference, AdapterOutput
from .config import CertManagerConfig


class CertManagerScripts(str, Enum):
    """Script resource paths"""
    # Post-work (1 script)
    WAIT_CERT_MANAGER = "post_work/wait-cert_manager.sh"
    
    # Validation (1 script)
    VALIDATE_CERT_MANAGER = "validation/validate-cert_manager.sh"


class CertManagerAdapter(PlatformAdapter):
    """Cert-manager certificate management adapter"""
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata"""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        return yaml.safe_load(metadata_path.read_text())
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return CertManagerConfig
    
    def init(self) -> List[ScriptReference]:
        """Cert-manager adapter has no init scripts"""
        return []
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Interactive prompts for ztc init"""
        return [
            InputPrompt(
                name="version",
                prompt="Cert-manager Version",
                type="string",
                default="v1.19.2",
                help_text="Cert-manager version to install (e.g., v1.19.2)"
            ),
            InputPrompt(
                name="namespace",
                prompt="Namespace",
                type="string",
                default="cert_manager",
                help_text="Kubernetes namespace for cert_manager"
            ),
            InputPrompt(
                name="enable_gateway_api",
                prompt="Enable Gateway API",
                type="boolean",
                default=True,
                help_text="Enable Gateway API support"
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
        """Wait for cert_manager readiness"""
        config = CertManagerConfig(**self.config)
        
        return [
            ScriptReference(
                package="workflow_engine.adapters.cert_manager.scripts",
                resource=CertManagerScripts.WAIT_CERT_MANAGER,
                description="Wait for cert_manager pods",
                timeout=300,
                context_data={
                    "namespace": config.namespace,
                    "timeout_seconds": 300,
                    "check_interval": 5
                }
            )
        ]
    
    def validation_scripts(self) -> List[ScriptReference]:
        """Cert-manager deployment validation"""
        config = CertManagerConfig(**self.config)
        
        return [
            ScriptReference(
                package="workflow_engine.adapters.cert_manager.scripts",
                resource=CertManagerScripts.VALIDATE_CERT_MANAGER,
                description="Validate cert_manager health",
                timeout=60,
                context_data={
                    "namespace": config.namespace
                }
            )
        ]
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate cert_manager ArgoCD Application manifest"""
        config = CertManagerConfig(**self.config)
        
        manifests = {}
        
        # Template context
        template_ctx = {
            "version": config.version,
            "namespace": config.namespace,
            "enable_gateway_api": config.enable_gateway_api,
            "mode": config.mode
        }
        
        # Render ArgoCD Application
        app_template = self.jinja_env.get_template("cert_manager/application.yaml.j2")
        manifests["argocd/base/01-cert-manager.yaml"] = await app_template.render_async(**template_ctx)
        
        # Certificate management capability data (empty - not a registered capability yet)
        capability_data = {}
        
        return AdapterOutput(
            manifests=manifests,
            stages=[],
            env_vars={},
            capabilities=capability_data,
            data={}
        )

    def get_stage_context(self, stage_name: str, all_adapters_config: Dict[str, Any]) -> Dict[str, Any]:
        """Return non-sensitive context for Cert Manager bootstrap stages"""
        return {
            'version': self.config['version'],
        }
