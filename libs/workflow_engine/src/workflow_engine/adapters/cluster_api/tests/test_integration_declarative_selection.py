"""Integration test: Verify declarative selection generates cluster_api block."""

import pytest
import yaml
from workflow_engine.engine.init_workflow import InitWorkflow
from workflow_engine.registry.adapter_registry import AdapterRegistry
from workflow_engine.adapters.cluster_api import ClusterAPIAdapter


@pytest.mark.integration
def test_declarative_selection_generates_cluster_api_block():
    """
    Integration test for task 1.4:
    - Uses InitWorkflow with cluster_api adapter registered
    - Simulates user selecting lifecycle_engine="declarative"
    - Verifies platform.yaml contains cluster_api adapter block
    - No cleanup needed (no external resources)
    """
    # Create registry and register cluster_api adapter
    registry = AdapterRegistry(auto_discover=False)
    registry.register(ClusterAPIAdapter)
    
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
    
    # Answer lifecycle_engine = declarative
    result = workflow.answer(state, "declarative")
    state = result["workflow_state"]
    
    # Answer management_topology
    result = workflow.answer(state, "enterprise")
    state = result["workflow_state"]
    
    # Answer cluster_api selection (if prompted)
    if not result.get("completed"):
        result = workflow.answer(state, "cluster_api")
        state = result["workflow_state"]
    
    # Answer cluster_api configuration inputs
    while not result.get("completed"):
        question = result.get("question", {})
        question_id = question.get("id", "")
        
        if "control_plane_machine_type" in question_id:
            result = workflow.answer(state, "CX33")
        elif "control_plane_replicas" in question_id:
            result = workflow.answer(state, "3")
        elif "worker_pool_name" in question_id:
            result = workflow.answer(state, "default")
        elif "worker_pool_machine_type" in question_id:
            result = workflow.answer(state, "CX33")
        elif "worker_pool_min_size" in question_id:
            result = workflow.answer(state, "1")
        elif "worker_pool_max_size" in question_id:
            result = workflow.answer(state, "5")
        else:
            break
        
        state = result["workflow_state"]
    
    # Verify workflow completed
    assert result.get("completed"), "Workflow did not complete"
    
    # Parse platform.yaml
    platform_yaml = result.get("platform_yaml")
    assert platform_yaml, "platform_yaml not generated"
    
    platform_data = yaml.safe_load(platform_yaml)
    
    # Verify cluster_api block exists
    assert "cluster_api" in platform_data["adapters"], "cluster_api block missing from platform.yaml"
    
    cluster_api_config = platform_data["adapters"]["cluster_api"]
    
    # Verify control_plane configuration
    assert "control_plane" in cluster_api_config
    assert cluster_api_config["control_plane"]["machine_type"] == "cx23"
    assert cluster_api_config["control_plane"]["replicas"] == 3
    
    # Verify worker_pools configuration
    assert "worker_pools" in cluster_api_config
    assert len(cluster_api_config["worker_pools"]) == 1
    
    worker_pool = cluster_api_config["worker_pools"][0]
    assert worker_pool["name"] == "default"
    assert worker_pool["machine_type"] == "ax41-nvme"
    assert worker_pool["min_size"] == 1
    assert worker_pool["max_size"] == 5
