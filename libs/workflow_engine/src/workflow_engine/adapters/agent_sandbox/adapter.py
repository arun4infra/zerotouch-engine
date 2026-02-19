"""Agent Sandbox adapter for Kubernetes agent runtime environments"""

from typing import List, Type, Dict, Any
from pathlib import Path
from pydantic import BaseModel
import yaml
from workflow_engine.adapters.base import PlatformAdapter, InputPrompt, ScriptReference, AdapterOutput
from .config import AgentSandboxConfig


class AgentSandboxAdapter(PlatformAdapter):
    """Agent Sandbox controller adapter"""
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata from Agent Sandbox adapter directory"""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        return yaml.safe_load(metadata_path.read_text())
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return AgentSandboxConfig
    
    def init(self) -> List[ScriptReference]:
        """Agent Sandbox adapter has no init scripts"""
        return []
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Interactive prompts for ztc init"""
        return [
            InputPrompt(
                name="image_registry",
                prompt="Image Registry",
                type="string",
                default="us-central1-docker.pkg.dev/k8s-staging-images/agent_sandbox",
                help_text="Container registry for agent_sandbox controller image"
            ),
            InputPrompt(
                name="image_tag",
                prompt="Image Tag",
                type="string",
                default="latest-main",
                help_text="Image tag for agent_sandbox controller"
            ),
            InputPrompt(
                name="namespace",
                prompt="Namespace",
                type="string",
                default="agent_sandbox-system",
                help_text="Kubernetes namespace for agent_sandbox controller"
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
        """Pre-work scripts (none for agent_sandbox)"""
        return []
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """Core bootstrap scripts (none - ArgoCD handles deployment)"""
        return []
    
    def post_work_scripts(self) -> List[ScriptReference]:
        """Post-work scripts (none for agent_sandbox)"""
        return []
    
    def validation_scripts(self) -> List[ScriptReference]:
        """Validation scripts (none - no legacy validation exists)"""
        return []
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate Agent Sandbox manifests"""
        config = AgentSandboxConfig(**self.config)
        
        manifests = {}
        
        # Template context
        template_ctx = {
            "image_registry": config.image_registry,
            "image_tag": config.image_tag,
            "namespace": config.namespace,
            "mode": config.mode,
            "platform_repo_url": "https://github.com/arun4infra/zerotouch-platform.git",
            "platform_repo_branch": "main"
        }
        
        # Render application manifest
        app_template = self.jinja_env.get_template("agent_sandbox/application.yaml.j2")
        manifests["argocd/base/04-agent-sandbox.yaml"] = await app_template.render_async(**template_ctx)
        
        # Render wrapper kustomization
        wrapper_template = self.jinja_env.get_template("agent_sandbox/wrapper/kustomization.yaml.j2")
        manifests["argocd/base/agent-sandbox-wrapper/kustomization.yaml"] = await wrapper_template.render_async(**template_ctx)
        
        # Agent sandbox capability data (empty for now)
        capability_data = {}
        
        return AdapterOutput(
            manifests=manifests,
            stages=[],
            env_vars={},
            capabilities=capability_data,
            data={}
        )
