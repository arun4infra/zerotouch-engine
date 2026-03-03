"""Integration test: Verify complete CAPI resource generation from platform.yaml."""

import pytest
import yaml
from workflow_engine.adapters.cluster_api.adapter import ClusterAPIAdapter
from workflow_engine.engine.context import ContextSnapshot


@pytest.mark.integration
def test_capi_resource_generation_from_platform_yaml():
    """
    Integration test for task 2.5:
    - Uses ClusterAPIAdapter render() method
    - Verifies all required CAPI resources are generated
    - Checks: Cluster, TalosControlPlane, HetznerMachineTemplate, MachineDeployment, MachineHealthCheck
    - No cleanup needed (no external resources)
    """
    # Create adapter with cluster_api configuration
    adapter_config = {
        "control_plane_machine_type": "cx23",
        "control_plane_replicas": 3,
        "worker_pool_name": "default",
        "worker_pool_machine_type": "cx23",
        "worker_pool_min_size": 2,
        "worker_pool_max_size": 10
    }
    
    adapter = ClusterAPIAdapter(config=adapter_config)
    
    # Create context snapshot with platform config
    platform_config = {
        "name": "test-cluster",
        "environment": "dev",
        "lifecycle_engine": "declarative"
    }
    
    ctx = ContextSnapshot(
        capabilities={},
        outputs={},
        platform_config=platform_config,
        adapters_config={"cluster_api": adapter_config},
        env_vars={}
    )
    
    # Render CAPI manifests
    import asyncio
    output = asyncio.run(adapter.render(ctx))
    
    # Verify manifests were generated
    assert output.manifests, "No manifests generated"
    
    # Verify Cluster resource exists
    assert "cluster.yaml" in output.manifests, "Cluster resource missing"
    cluster_yaml = yaml.safe_load(output.manifests["cluster.yaml"])
    assert cluster_yaml["kind"] == "Cluster"
    assert cluster_yaml["metadata"]["name"] == "test-cluster"
    
    # Verify TalosControlPlane resource exists
    assert "talos-control-plane.yaml" in output.manifests, "TalosControlPlane resource missing"
    tcp_yaml = yaml.safe_load(output.manifests["talos-control-plane.yaml"])
    assert tcp_yaml["kind"] == "TalosControlPlane"
    assert tcp_yaml["spec"]["replicas"] == 3
    
    # Verify control plane HetznerMachineTemplate exists
    assert "control-plane-machine-template.yaml" in output.manifests, "Control plane HetznerMachineTemplate missing"
    cp_hmt_yaml = yaml.safe_load(output.manifests["control-plane-machine-template.yaml"])
    assert cp_hmt_yaml["kind"] == "HetznerMachineTemplate"
    assert cp_hmt_yaml["spec"]["template"]["spec"]["type"] == "cpx31"
    
    # Verify worker pool MachineDeployment exists
    assert "machine-deployment-default.yaml" in output.manifests, "MachineDeployment missing"
    md_yaml = yaml.safe_load(output.manifests["machine-deployment-default.yaml"])
    assert md_yaml["kind"] == "MachineDeployment"
    assert md_yaml["metadata"]["name"] == "default"
    assert md_yaml["spec"]["replicas"] == 2
    assert md_yaml["metadata"]["annotations"]["cluster.x-k8s.io/cluster-api-autoscaler-node-group-min-size"] == "2"
    assert md_yaml["metadata"]["annotations"]["cluster.x-k8s.io/cluster-api-autoscaler-node-group-max-size"] == "10"
    
    # Verify worker pool HetznerMachineTemplate exists
    assert "hetzner-machine-template-default.yaml" in output.manifests, "Worker HetznerMachineTemplate missing"
    worker_hmt_yaml = yaml.safe_load(output.manifests["hetzner-machine-template-default.yaml"])
    assert worker_hmt_yaml["kind"] == "HetznerMachineTemplate"
    assert worker_hmt_yaml["spec"]["template"]["spec"]["type"] == "ax41-nvme"
    
    # Verify MachineHealthCheck exists
    assert "machine-health-check-default.yaml" in output.manifests, "MachineHealthCheck missing"
    mhc_yaml = yaml.safe_load(output.manifests["machine-health-check-default.yaml"])
    assert mhc_yaml["kind"] == "MachineHealthCheck"
    assert mhc_yaml["spec"]["nodeStartupTimeout"] == "15m"
    assert mhc_yaml["spec"]["maxUnhealthy"] == "40%"
