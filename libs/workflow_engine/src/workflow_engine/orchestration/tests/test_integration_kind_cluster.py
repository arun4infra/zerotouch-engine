"""Integration tests for Kind cluster management

CRITICAL: These tests use REAL infrastructure - no mocking.
- Requires Docker daemon running
- Creates actual Kind clusters
- Requires kind binary installed
"""

import pytest
from pathlib import Path

from workflow_engine.orchestration.kind_cluster_manager import (
    KindClusterManager,
    KindClusterConfig
)


@pytest.mark.integration
def test_kind_cluster_creation_and_cleanup():
    """Verify Kind cluster creation with randomized API port and cleanup
    
    Validates: Requirements 3.1, 3.9
    """
    # Create manager with test cluster name
    config = KindClusterConfig(name="ztc-test-bootstrap")
    manager = KindClusterManager(config)
    
    try:
        # Verify cluster doesn't exist initially
        assert not manager.cluster_exists(), "Cluster should not exist before creation"
        
        # Create cluster
        kubeconfig_path = manager.create_cluster()
        
        # Verify cluster exists
        assert manager.cluster_exists(), "Cluster should exist after creation"
        
        # Verify kubeconfig file created
        assert kubeconfig_path.exists(), "Kubeconfig file should exist"
        assert kubeconfig_path == config.kubeconfig_path, "Kubeconfig path should match config"
        
        # Verify kubeconfig is valid (contains cluster info)
        kubeconfig_content = kubeconfig_path.read_text()
        assert "ztc-test-bootstrap" in kubeconfig_content, "Kubeconfig should reference cluster name"
        assert "server:" in kubeconfig_content, "Kubeconfig should contain server endpoint"
        
    finally:
        # Cleanup: delete cluster
        success = manager.delete_cluster()
        assert success, "Cluster deletion should succeed"
        
        # Verify cluster deleted
        assert not manager.cluster_exists(), "Cluster should not exist after deletion"
        
        # Verify kubeconfig cleaned up
        assert not config.kubeconfig_path.exists(), "Kubeconfig should be deleted"


@pytest.mark.integration
def test_kind_cluster_deletion_retry():
    """Verify Kind cluster deletion with exponential backoff retry
    
    Validates: Requirements 4.11, 4.12
    """
    config = KindClusterConfig(name="ztc-test-retry")
    manager = KindClusterManager(config)
    
    try:
        # Create cluster
        manager.create_cluster()
        assert manager.cluster_exists()
        
        # Delete with retry
        success = manager.delete_cluster(max_retries=3)
        assert success, "Deletion should succeed within retry limit"
        
    finally:
        # Ensure cleanup even if test fails
        if manager.cluster_exists():
            manager.delete_cluster()


@pytest.mark.integration
def test_kind_cluster_randomized_api_port():
    """Verify Kind cluster uses randomized API port to prevent CI collisions
    
    Validates: Requirements 3.1
    """
    config = KindClusterConfig(name="ztc-test-port")
    manager = KindClusterManager(config)
    
    try:
        # Create cluster without specifying port
        kubeconfig_path = manager.create_cluster()
        
        # Verify kubeconfig contains non-default port
        kubeconfig_content = kubeconfig_path.read_text()
        
        # Default kind port is 6443, randomized should be 30000-32767
        assert "server:" in kubeconfig_content
        # Port should be in NodePort range
        assert any(str(port) in kubeconfig_content for port in range(30000, 32768))
        
    finally:
        manager.delete_cluster()
