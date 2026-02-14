"""KEDA adapter for event-driven autoscaling"""

from enum import Enum
from typing import List, Type, Dict, Any
from pathlib import Path
from pydantic import BaseModel
import yaml
from ztc.adapters.base import PlatformAdapter, InputPrompt, ScriptReference, AdapterOutput
from .config import KEDAConfig


class KEDAScripts(str, Enum):
    """Script resource paths"""
    # Post-work (1 script)
    WAIT_KEDA = "post_work/wait-keda.sh"
    
    # Validation (1 script)
    VALIDATE_KEDA = "validation/validate-keda.sh"


class KEDAAdapter(PlatformAdapter):
    """KEDA event-driven autoscaling adapter"""
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata"""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        return yaml.safe_load(metadata_path.read_text())
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return KEDAConfig
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Interactive prompts for ztc init"""
        return [
            InputPrompt(
                name="version",
                prompt="KEDA Version",
                type="string",
                default="2.18.1",
                help_text="KEDA version to install (e.g., 2.18.1)"
            ),
            InputPrompt(
                name="namespace",
                prompt="Namespace",
                type="string",
                default="keda",
                help_text="Kubernetes namespace for KEDA"
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
        """Wait for KEDA readiness"""
        config = KEDAConfig(**self.config)
        
        return [
            ScriptReference(
                package="ztc.adapters.keda.scripts",
                resource=KEDAScripts.WAIT_KEDA,
                description="Wait for KEDA operator",
                timeout=300,
                context_data={
                    "namespace": config.namespace,
                    "timeout_seconds": 300,
                    "check_interval": 5
                }
            )
        ]
    
    def validation_scripts(self) -> List[ScriptReference]:
        """KEDA deployment validation"""
        config = KEDAConfig(**self.config)
        
        return [
            ScriptReference(
                package="ztc.adapters.keda.scripts",
                resource=KEDAScripts.VALIDATE_KEDA,
                description="Validate KEDA health",
                timeout=60,
                context_data={
                    "namespace": config.namespace
                }
            )
        ]
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate KEDA ArgoCD Application manifest"""
        config = KEDAConfig(**self.config)
        
        manifests = {}
        
        # Template context
        template_ctx = {
            "version": config.version,
            "namespace": config.namespace,
            "mode": config.mode
        }
        
        # Render ArgoCD Application
        app_template = self.jinja_env.get_template("keda/application.yaml.j2")
        manifests["argocd/overlays/main/core/04-keda.yaml"] = await app_template.render_async(**template_ctx)
        
        # Autoscaling capability data (empty - not a registered capability yet)
        capability_data = {}
        
        return AdapterOutput(
            manifests=manifests,
            stages=[],
            env_vars={},
            capabilities=capability_data,
            data={}
        )
