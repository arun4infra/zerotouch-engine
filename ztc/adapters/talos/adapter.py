"""Talos OS adapter implementation"""

from typing import List, Dict, Any, Type, Literal
from pydantic import BaseModel, Field
from pathlib import Path
from enum import Enum
import yaml

from ztc.adapters.base import (
    PlatformAdapter,
    InputPrompt,
    ScriptReference,
    AdapterOutput,
)
from ztc.interfaces.capabilities import KubernetesAPICapability


class NodeConfig(BaseModel):
    """Node configuration for Talos"""
    name: str = Field(..., pattern=r"^[a-z0-9-]+$")
    ip: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    role: Literal["controlplane", "worker"]


class TalosConfig(BaseModel):
    """Talos adapter configuration with validation"""
    version: str
    factory_image_id: str = Field(..., min_length=64, max_length=64)
    cluster_name: str = Field(..., pattern=r"^[a-z0-9-]+$")
    cluster_endpoint: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$")
    nodes: List[NodeConfig]
    disk_device: str = "/dev/sda"
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "version": "v1.11.5",
                "factory_image_id": "a" * 64,
                "cluster_name": "production",
                "cluster_endpoint": "46.62.218.181:6443",
                "nodes": [
                    {"name": "cp01", "ip": "46.62.218.181", "role": "controlplane"}
                ],
                "disk_device": "/dev/sda"
            }
        }
    }


class TalosScripts(str, Enum):
    """Talos adapter script resources (validated at class load time)"""
    ENABLE_RESCUE = "pre_work/enable-rescue-mode.sh"
    EMBED_NETWORK = "bootstrap/embed-network-manifests.sh"
    INSTALL = "bootstrap/install-talos.sh"
    BOOTSTRAP = "bootstrap/bootstrap-talos.sh"
    ADD_WORKERS = "bootstrap/add-worker-nodes.sh"
    VALIDATE_CLUSTER = "validation/validate-cluster.sh"


class TalosAdapter(PlatformAdapter):
    """Talos OS adapter"""
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return TalosConfig
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Return interactive prompts for Talos configuration"""
        return [
            InputPrompt(
                name="version",
                prompt="Select Talos version",
                type="choice",
                choices=["v1.10.x", "v1.11.5"],
                default="v1.11.5",
                help_text="Recommended: v1.11.5"
            ),
            InputPrompt(
                name="factory_image_id",
                prompt="Talos factory image ID",
                type="string",
                default="376567988ad370138ad8b2698212367b8edcb69b5fd68c80be1f2ec7d603b4ba",
                help_text="Custom Talos image with embedded extensions"
            ),
            InputPrompt(
                name="cluster_name",
                prompt="Cluster name (e.g., kube-prod)",
                type="string",
                validation=r"^[a-z0-9-]+$",
                help_text="Alphanumeric + hyphens only"
            ),
            InputPrompt(
                name="cluster_endpoint",
                prompt="Cluster API endpoint",
                type="string",
                validation=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$",
                help_text="Format: IP:PORT (e.g., 46.62.218.181:6443)"
            ),
            InputPrompt(
                name="nodes",
                prompt="Node definitions (JSON array)",
                type="json",
                help_text='[{"name": "cp01", "ip": "46.62.218.181", "role": "controlplane"}]'
            )
        ]
    
    def pre_work_scripts(self) -> List[ScriptReference]:
        """Return pre-work scripts"""
        return []
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """Return bootstrap scripts with context_data"""
        config = TalosConfig(**self.config)
        
        return [
            ScriptReference(
                package="ztc.adapters.talos.scripts",
                resource=TalosScripts.EMBED_NETWORK,
                description="Embed Gateway API CRDs and Cilium CNI in Talos config",
                timeout=60,
                context_data={
                    "cluster_name": config.cluster_name
                }
            ),
            ScriptReference(
                package="ztc.adapters.talos.scripts",
                resource=TalosScripts.INSTALL,
                description="Install Talos OS on bare-metal server",
                timeout=600,
                context_data={
                    "nodes": [node.model_dump() for node in config.nodes],
                    "factory_image_id": config.factory_image_id,
                    "disk_device": config.disk_device
                }
            ),
            ScriptReference(
                package="ztc.adapters.talos.scripts",
                resource=TalosScripts.BOOTSTRAP,
                description="Bootstrap Talos cluster",
                timeout=300,
                context_data={
                    "cluster_endpoint": config.cluster_endpoint,
                    "controlplane_ip": next(n.ip for n in config.nodes if n.role == "controlplane")
                }
            ),
            ScriptReference(
                package="ztc.adapters.talos.scripts",
                resource=TalosScripts.ADD_WORKERS,
                description="Add worker nodes to cluster",
                timeout=300,
                context_data={
                    "worker_nodes": [n.model_dump() for n in config.nodes if n.role == "worker"]
                }
            )
        ]
    
    def post_work_scripts(self) -> List[ScriptReference]:
        """Talos doesn't have post-work scripts"""
        return []
    
    def validation_scripts(self) -> List[ScriptReference]:
        """Return verification scripts"""
        return [
            ScriptReference(
                package="ztc.adapters.talos.scripts",
                resource=TalosScripts.VALIDATE_CLUSTER,
                description="Verify nodes joined cluster",
                timeout=60,
                context_data={
                    "expected_nodes": len(self.config["nodes"])
                }
            )
        ]
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate Talos machine configs per node"""
        config = TalosConfig(**self.config)
        
        manifests = {}
        
        # Render per-node configs
        for node in config.nodes:
            template_name = f"talos/{node.role}.yaml.j2"
            template = self.jinja_env.get_template(template_name)
            
            # Get CNI manifests from context
            cni_manifests = ""
            if ctx and hasattr(ctx, 'get_capability_data'):
                cni_data = ctx.get_capability_data('cni')
                if cni_data:
                    cni_manifests = cni_data.manifests
            
            node_config = await template.render_async(
                cluster_name=config.cluster_name,
                cluster_endpoint=config.cluster_endpoint,
                node_name=node.name,
                node_ip=node.ip,
                disk_device=config.disk_device,
                cni_manifests=cni_manifests
            )
            
            manifests[f"talos/nodes/{node.name}/config.yaml"] = node_config
        
        # Generate talosconfig
        talosconfig_template = self.jinja_env.get_template("talos/talosconfig.j2")
        talosconfig = await talosconfig_template.render_async(
            cluster_name=config.cluster_name,
            cluster_endpoint=config.cluster_endpoint
        )
        manifests["talos/talosconfig"] = talosconfig
        
        # Create Kubernetes API capability
        k8s_capability = KubernetesAPICapability(
            cluster_endpoint=config.cluster_endpoint,
            kubeconfig_path=f"/path/to/{config.cluster_name}/kubeconfig",
            version=">=1.28"
        )
        
        return AdapterOutput(
            manifests=manifests,
            stages=[],
            env_vars={
                "CLUSTER_NAME": config.cluster_name,
                "CLUSTER_ENDPOINT": config.cluster_endpoint
            },
            capabilities={
                "kubernetes-api": k8s_capability
            },
            data={
                "cluster_endpoint": config.cluster_endpoint,
                "nodes": [node.model_dump() for node in config.nodes]
            }
        )
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata"""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        if not metadata_path.exists():
            return {
                "name": "talos",
                "version": "1.0.0",
                "phase": "foundation",
                "selection_group": "os",
                "is_default": True,
                "provides": [
                    {"capability": "kubernetes-api", "version": ">=1.28"}
                ],
                "requires": [
                    {"capability": "cloud-infrastructure", "version": "v1.0"},
                    {"capability": "cni", "version": "v1.0"}
                ]
            }
        return yaml.safe_load(metadata_path.read_text())
