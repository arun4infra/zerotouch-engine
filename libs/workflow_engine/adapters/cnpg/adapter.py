"""CNPG adapter for PostgreSQL operator"""

from enum import Enum
from typing import List, Type, Dict, Any
from pathlib import Path
from pydantic import BaseModel
import yaml
from workflow_engine.adapters.base import PlatformAdapter, InputPrompt, ScriptReference, AdapterOutput
from .config import CNPGConfig


class CNPGScripts(str, Enum):
    """Script resource paths"""
    # Post-work (1 script)
    WAIT_CNPG = "post_work/wait-cnpg.sh"
    
    # Validation (1 script)
    VALIDATE_CNPG = "validation/validate-cnpg.sh"


class CNPGAdapter(PlatformAdapter):
    """CNPG PostgreSQL operator adapter"""
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata"""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        return yaml.safe_load(metadata_path.read_text())
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return CNPGConfig
    
    def init(self) -> List[ScriptReference]:
        """CNPG adapter has no init scripts"""
        return []
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Interactive prompts for ztc init"""
        return [
            InputPrompt(
                name="version",
                prompt="CNPG Version",
                type="string",
                default="0.27.0",
                help_text="CNPG version to install (e.g., 0.27.0)"
            ),
            InputPrompt(
                name="namespace",
                prompt="Namespace",
                type="string",
                default="cnpg-system",
                help_text="Kubernetes namespace for CNPG"
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
        """Wait for CNPG readiness"""
        config = CNPGConfig(**self.config)
        
        return [
            ScriptReference(
                package="workflow_engine.adapters.cnpg.scripts",
                resource=CNPGScripts.WAIT_CNPG,
                description="Wait for CNPG operator",
                timeout=300,
                context_data={
                    "namespace": config.namespace,
                    "timeout_seconds": 300,
                    "check_interval": 5
                }
            )
        ]
    
    def validation_scripts(self) -> List[ScriptReference]:
        """CNPG deployment validation"""
        config = CNPGConfig(**self.config)
        
        return [
            ScriptReference(
                package="workflow_engine.adapters.cnpg.scripts",
                resource=CNPGScripts.VALIDATE_CNPG,
                description="Validate CNPG health",
                timeout=60,
                context_data={
                    "namespace": config.namespace
                }
            )
        ]
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate CNPG ArgoCD Application manifest"""
        config = CNPGConfig(**self.config)
        
        manifests = {}
        
        # Template context
        template_ctx = {
            "version": config.version,
            "namespace": config.namespace,
            "mode": config.mode
        }
        
        # Render ArgoCD Application
        app_template = self.jinja_env.get_template("cnpg/application.yaml.j2")
        manifests["argocd/overlays/main/core/02-cnpg.yaml"] = await app_template.render_async(**template_ctx)
        
        # Database operator capability data (empty - not a registered capability yet)
        capability_data = {}
        
        return AdapterOutput(
            manifests=manifests,
            stages=[],
            env_vars={},
            capabilities=capability_data,
            data={}
        )
