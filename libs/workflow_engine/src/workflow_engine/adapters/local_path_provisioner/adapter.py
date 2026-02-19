"""Local Path Provisioner adapter for local storage"""

from typing import List, Type, Dict, Any
from pathlib import Path
from pydantic import BaseModel
import yaml
from workflow_engine.adapters.base import PlatformAdapter, InputPrompt, ScriptReference, AdapterOutput
from workflow_engine.interfaces.capabilities import LocalStorageCapability
from .config import LocalPathProvisionerConfig


class LocalPathProvisionerAdapter(PlatformAdapter):
    """Local Path Provisioner storage adapter"""
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata"""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        return yaml.safe_load(metadata_path.read_text())
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return LocalPathProvisionerConfig
    
    def init(self) -> List[ScriptReference]:
        """No init scripts"""
        return []
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Interactive prompts for ztc init"""
        return [
            InputPrompt(
                name="version",
                prompt="Local Path Provisioner Version",
                type="string",
                default="v0.0.28",
                help_text="Version to install"
            ),
            InputPrompt(
                name="namespace",
                prompt="Namespace",
                type="string",
                default="local-path-storage",
                help_text="Kubernetes namespace"
            ),
            InputPrompt(
                name="mode",
                prompt="Deployment Mode",
                type="choice",
                choices=["production", "preview"],
                default="production",
                help_text="Production or Preview mode"
            )
        ]
    
    def pre_work_scripts(self) -> List[ScriptReference]:
        """No pre-work scripts"""
        return []
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """No bootstrap scripts - ArgoCD handles deployment"""
        return []
    
    def post_work_scripts(self) -> List[ScriptReference]:
        """No post-work scripts"""
        return []
    
    def validation_scripts(self) -> List[ScriptReference]:
        """No validation scripts"""
        return []
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate Local Path Provisioner ArgoCD Application manifest"""
        config = LocalPathProvisionerConfig(**self.config)
        
        manifests = {}
        
        # Template context
        template_ctx = {
            "version": config.version,
            "namespace": config.namespace,
            "mode": config.mode
        }
        
        # Render ArgoCD Application
        app_template = self.jinja_env.get_template("local_path_provisioner/application.yaml.j2")
        manifests["argocd/k8/core/00-local-path-provisioner.yaml"] = await app_template.render_async(**template_ctx)
        
        # Create capability instance
        capability = LocalStorageCapability(
            provider="local-path",
            storage_class="local-path",
            namespace=config.namespace
        )
        
        return AdapterOutput(
            manifests=manifests,
            stages=[],
            env_vars={},
            capabilities={"local-storage": capability},
            data={}
        )
