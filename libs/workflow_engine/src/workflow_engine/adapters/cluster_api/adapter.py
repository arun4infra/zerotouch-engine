"""Cluster API adapter for declarative infrastructure management."""

from typing import List, Type, Dict, Any
from pathlib import Path
import yaml
from pydantic import BaseModel
from workflow_engine.adapters.base import PlatformAdapter, InputPrompt, ScriptReference, AdapterOutput
from .config import ClusterAPIConfig, ControlPlaneConfig, WorkerPoolConfig


class ClusterAPIAdapter(PlatformAdapter):
    """Cluster API adapter for declarative lifecycle management."""
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata."""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        return yaml.safe_load(metadata_path.read_text())
    
    def get_stage_context(self, stage_name: str, all_adapters_config: Dict[str, Any]) -> Dict[str, Any]:
        """Return non-sensitive context for cluster_api stages."""
        return {}
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return ClusterAPIConfig
    
    def clean_config(self, config: dict) -> dict:
        """Transform flat fields to nested structure for platform.yaml."""
        # Instantiate model to trigger transformation
        model_instance = ClusterAPIConfig(**config)
        
        # Return only nested fields
        return {
            "control_plane": {
                "machine_type": model_instance.control_plane.machine_type,
                "replicas": model_instance.control_plane.replicas
            },
            "worker_pools": [
                {
                    "name": wp.name,
                    "machine_type": wp.machine_type,
                    "min_size": wp.min_size,
                    "max_size": wp.max_size
                }
                for wp in model_instance.worker_pools
            ]
        }
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Interactive prompts for cluster_api configuration."""
        return [
            InputPrompt(
                name="control_plane_machine_type",
                prompt="Control Plane Machine Type",
                type="string",
                default="cpx31",
                help_text="Hetzner machine type for control plane nodes"
            ),
            InputPrompt(
                name="control_plane_replicas",
                prompt="Control Plane Replicas",
                type="integer",
                default=3,
                help_text="Number of control plane nodes"
            ),
            InputPrompt(
                name="worker_pool_name",
                prompt="Worker Pool Name",
                type="string",
                default="default",
                help_text="Name for the worker pool"
            ),
            InputPrompt(
                name="worker_pool_machine_type",
                prompt="Worker Machine Type",
                type="string",
                default="ax41-nvme",
                help_text="Hetzner machine type for worker nodes"
            ),
            InputPrompt(
                name="worker_pool_min_size",
                prompt="Worker Pool Min Size",
                type="integer",
                default=1,
                help_text="Minimum number of worker nodes"
            ),
            InputPrompt(
                name="worker_pool_max_size",
                prompt="Worker Pool Max Size",
                type="integer",
                default=5,
                help_text="Maximum number of worker nodes"
            )
        ]
    
    def init(self) -> List[ScriptReference]:
        """No init scripts for cluster_api adapter."""
        return []
    
    def pre_work_scripts(self) -> List[ScriptReference]:
        """No pre-work scripts."""
        return []
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """No bootstrap scripts."""
        return []
    
    def post_work_scripts(self) -> List[ScriptReference]:
        """No post-work scripts."""
        return []
    
    def validation_scripts(self) -> List[ScriptReference]:
        """No validation scripts."""
        return []
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate CAPI manifests."""
        config = ClusterAPIConfig(**self.config)
        
        # Get versions from VersionProvider
        kubernetes_version = self._get_version_config('cluster_api', 'default_kubernetes_version')
        talos_version = self._get_version_config('cluster_api', 'default_talos_version')
        talos_installer_image = self._get_version_config('cluster_api', 'default_talos_installer_image')
        hcloud_base_image = self._get_version_config('cluster_api', 'default_hcloud_base_image')
        
        if not all([kubernetes_version, talos_version, talos_installer_image, hcloud_base_image]):
            raise ValueError("Missing required CAPI version configuration in versions.yaml")
        
        # Get cluster name from platform config
        cluster_name = ctx.platform_config.get('name', 'cluster')
        
        # Load Jinja2 environment
        from jinja2 import Environment, FileSystemLoader
        template_dir = Path(__file__).parent / "templates"
        jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))
        
        manifests = {}
        
        # Render HetznerCluster resource (must come before Cluster)
        hetzner_cluster_template = jinja_env.get_template("hetzner-cluster.yaml.j2")
        manifests["hetzner-cluster.yaml"] = hetzner_cluster_template.render(cluster_name=cluster_name)
        
        # Render Cluster resource
        cluster_template = jinja_env.get_template("cluster.yaml.j2")
        manifests["cluster.yaml"] = cluster_template.render(cluster_name=cluster_name)
        
        # Render TalosControlPlane resource
        cp_template = jinja_env.get_template("talos-control-plane.yaml.j2")
        manifests["talos-control-plane.yaml"] = cp_template.render(
            cluster_name=cluster_name,
            control_plane_replicas=config.control_plane.replicas,
            kubernetes_version=kubernetes_version,
            talos_version=talos_version,
            talos_installer_image=talos_installer_image
        )
        
        # Render control plane HetznerMachineTemplate
        hmt_template = jinja_env.get_template("hetzner-machine-template.yaml.j2")
        manifests["control-plane-machine-template.yaml"] = hmt_template.render(
            cluster_name=cluster_name,
            pool_name="control-plane",
            machine_type=config.control_plane.machine_type,
            hcloud_base_image=hcloud_base_image
        )
        
        # Render worker pool resources
        md_template = jinja_env.get_template("machine-deployment.yaml.j2")
        mhc_template = jinja_env.get_template("machine-health-check.yaml.j2")
        tct_template = jinja_env.get_template("talos-config-template.yaml.j2")
        
        for pool in config.worker_pools:
            # MachineDeployment
            manifests[f"machine-deployment-{pool.name}.yaml"] = md_template.render(
                pool_name=pool.name,
                cluster_name=cluster_name,
                min_size=pool.min_size,
                max_size=pool.max_size
            )
            
            # HetznerMachineTemplate for worker pool
            manifests[f"hetzner-machine-template-{pool.name}.yaml"] = hmt_template.render(
                cluster_name=cluster_name,
                pool_name=pool.name,
                machine_type=pool.machine_type,
                hcloud_base_image=hcloud_base_image
            )
            
            # TalosConfigTemplate for worker pool
            manifests[f"talos-config-template-{pool.name}.yaml"] = tct_template.render(
                pool_name=pool.name,
                talos_version=talos_version,
                talos_installer_image=talos_installer_image
            )
            
            # MachineHealthCheck
            manifests[f"machine-health-check-{pool.name}.yaml"] = mhc_template.render(
                pool_name=pool.name,
                cluster_name=cluster_name
            )
        
        return AdapterOutput(
            manifests=manifests,
            stages=[],
            env_vars={},
            capabilities={},
            data={}
        )
    

