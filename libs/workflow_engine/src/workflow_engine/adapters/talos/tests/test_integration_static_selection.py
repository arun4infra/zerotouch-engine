"""Integration test: Verify static selection generates node definitions."""

import pytest
import yaml
from workflow_engine.engine.init_workflow import InitWorkflow
from workflow_engine.registry.adapter_registry import AdapterRegistry
from workflow_engine.adapters.talos.adapter import TalosAdapter


@pytest.mark.integration
def test_static_selection_generates_node_definitions():
    """
    Integration test for task 1.5:
    - Uses InitWorkflow with talos adapter registered
    - Simulates user selecting lifecycle_engine="static"
    - Verifies platform.yaml contains node definitions with IP addresses
    - No cleanup needed (no external resources)
    """
    # Create registry and register talos adapter
    registry = AdapterRegistry(auto_discover=False)
    registry.register(TalosAdapter)
    
    # Initialize workflow
    workflow = InitWorkflow(registry)
    
    # Start workflow
    result = workflow.start()
    state = result["workflow_state"]
    
    # Answer org_name
    result = workflow.answer(state, "testorg")
    state = result["workflow_state"]
    
    # Answer app_name
    result = workflow.answer(state, "testorg-app")
    state = result["workflow_state"]
    
    # Answer lifecycle_engine = static
    result = workflow.answer(state, "static")
    state = result["workflow_state"]
    
    # Answer talos selection (if prompted)
    if not result.get("completed") and result.get("question", {}).get("id", "").endswith("_selection"):
        result = workflow.answer(state, "talos")
        state = result["workflow_state"]
    
    # Answer talos configuration inputs
    while not result.get("completed"):
        question = result.get("question", {})
        question_id = question.get("id", "")
        
        if "version" in question_id:
            result = workflow.answer(state, "v1.11.5")
        elif "factory_image_id" in question_id:
            result = workflow.answer(state, "a" * 64)
        elif "cluster_name" in question_id:
            result = workflow.answer(state, "test-cluster")
        elif "cluster_endpoint" in question_id:
            result = workflow.answer(state, "46.62.218.181:6443")
        elif "nodes" in question_id:
            nodes = [
                {"name": "cp01", "ip": "46.62.218.181", "role": "controlplane"},
                {"name": "worker01", "ip": "46.62.218.182", "role": "worker"}
            ]
            result = workflow.answer(state, nodes)
        elif "disk_device" in question_id:
            result = workflow.answer(state, "/dev/sda")
        else:
            break
        
        state = result["workflow_state"]
    
    # Verify workflow completed
    assert result.get("completed"), "Workflow did not complete"
    
    # Parse platform.yaml
    platform_yaml = result.get("platform_yaml")
    assert platform_yaml, "platform_yaml not generated"
    
    platform_data = yaml.safe_load(platform_yaml)
    
    # Verify lifecycle_engine is static
    assert platform_data["platform"]["lifecycle_engine"] == "static", "lifecycle_engine should be static"
    
    # Verify talos block exists
    assert "talos" in platform_data["adapters"], "talos block missing from platform.yaml"
    
    talos_config = platform_data["adapters"]["talos"]
    
    # Verify nodes configuration exists
    assert "nodes" in talos_config, "nodes field missing from talos config"
    assert len(talos_config["nodes"]) == 2, "Expected 2 nodes"
    
    # Verify node definitions contain IP addresses
    cp_node = talos_config["nodes"][0]
    assert cp_node["name"] == "cp01"
    assert cp_node["ip"] == "46.62.218.181"
    assert cp_node["role"] == "controlplane"
    
    worker_node = talos_config["nodes"][1]
    assert worker_node["name"] == "worker01"
    assert worker_node["ip"] == "46.62.218.182"
    assert worker_node["role"] == "worker"
    
    # Verify cluster_endpoint contains IP
    assert talos_config["cluster_endpoint"] == "46.62.218.181:6443"
