"""NATS adapter for cloud-native messaging"""

from enum import Enum
from typing import List, Type, Dict, Any
from pathlib import Path
from pydantic import BaseModel
import yaml
from workflow_engine.adapters.base import PlatformAdapter, InputPrompt, ScriptReference, AdapterOutput
from .config import NATSConfig


class NATSScripts(str, Enum):
    """Script resource paths"""
    # Post-work (1 script)
    WAIT_NATS = "post_work/wait-nats.sh"
    
    # Validation (1 script)
    VALIDATE_NATS = "validation/validate-nats.sh"


class NATSAdapter(PlatformAdapter):
    """NATS cloud-native messaging adapter"""
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata"""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        return yaml.safe_load(metadata_path.read_text())
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return NATSConfig
    
    def init(self) -> List[ScriptReference]:
        """NATS adapter has no init scripts"""
        return []
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Interactive prompts for ztc init"""
        return [
            InputPrompt(
                name="version",
                prompt="NATS Version",
                type="string",
                default="1.2.6",
                help_text="NATS Helm chart version to install (e.g., 1.2.6)"
            ),
            InputPrompt(
                name="namespace",
                prompt="Namespace",
                type="string",
                default="nats",
                help_text="Kubernetes namespace for NATS"
            ),
            InputPrompt(
                name="jetstream_file_store_size",
                prompt="JetStream File Store Size",
                type="string",
                default="10Gi",
                help_text="JetStream file store size (e.g., 10Gi)"
            ),
            InputPrompt(
                name="jetstream_memory_store_size",
                prompt="JetStream Memory Store Size",
                type="string",
                default="1Gi",
                help_text="JetStream memory store size (e.g., 1Gi)"
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
        """Wait for NATS readiness"""
        config = NATSConfig(**self.config)
        
        return [
            ScriptReference(
                package="workflow_engine.adapters.nats.scripts",
                resource=NATSScripts.WAIT_NATS,
                description="Wait for NATS StatefulSet",
                timeout=300,
                context_data={
                    "namespace": config.namespace,
                    "timeout_seconds": 300,
                    "check_interval": 5
                }
            )
        ]
    
    def validation_scripts(self) -> List[ScriptReference]:
        """NATS deployment validation"""
        config = NATSConfig(**self.config)
        
        return [
            ScriptReference(
                package="workflow_engine.adapters.nats.scripts",
                resource=NATSScripts.VALIDATE_NATS,
                description="Validate NATS health",
                timeout=60,
                context_data={
                    "namespace": config.namespace
                }
            )
        ]
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate NATS ArgoCD Application manifest"""
        config = NATSConfig(**self.config)
        
        manifests = {}
        
        # Template context
        template_ctx = {
            "version": config.version,
            "namespace": config.namespace,
            "jetstream_file_store_size": config.jetstream_file_store_size,
            "jetstream_memory_store_size": config.jetstream_memory_store_size,
            "mode": config.mode
        }
        
        # Render ArgoCD Application
        app_template = self.jinja_env.get_template("nats/application.yaml.j2")
        manifests["argocd/base/05-nats.yaml"] = await app_template.render_async(**template_ctx)
        
        # Messaging capability data (empty - not a registered capability yet)
        capability_data = {}
        
        return AdapterOutput(
            manifests=manifests,
            stages=[],
            env_vars={},
            capabilities=capability_data,
            data={}
        )
