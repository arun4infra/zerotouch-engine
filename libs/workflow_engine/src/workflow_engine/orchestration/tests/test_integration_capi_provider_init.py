"""Integration tests for CAPI provider initialization

CRITICAL: These tests use REAL infrastructure - no mocking.
- Creates actual Kind clusters
- Initializes real CAPI providers
- Creates actual Hetzner VMs
- Requires HCLOUD_TOKEN environment variable
- Destroys all resources in finally blocks
"""

import pytest
import os
from pathlib import Path
from workflow_engine.orchestration.kind_cluster_manager import KindClusterManager, KindClusterConfig
from workflow_engine.orchestration.capi_provider_initializer import CAPIProviderInitializer, CAPIProviderConfig
from workflow_engine.orchestration.clusterctl_manager import ClusterctlManager


@pytest.mark.integration
def test_capi_provider_initialization():
    """Verify CAPI provider initialization on Kind cluster
    
    Validates: Requirements 3.2, 3.3
    Cleanup: Deletes Kind cluster
    """
    # Check for required credentials
    hcloud_token = os.environ.get("HCLOUD_TOKEN")
    if not hcloud_token:
        raise EnvironmentError("HCLOUD_TOKEN environment variable not set - required for CAPI provider initialization")
    
    # Download clusterctl if not available
    clusterctl_mgr = ClusterctlManager()
    clusterctl_path = None
    if not clusterctl_mgr.is_available():
        clusterctl_path = clusterctl_mgr.download(version="v1.12.3")
    
    # Create Kind cluster
    kind_config = KindClusterConfig(name="ztc-test-capi-init")
    kind_manager = KindClusterManager(kind_config)
    
    try:
        # Create Kind cluster
        kubeconfig_path = kind_manager.create_cluster()
        assert kubeconfig_path.exists(), "Kubeconfig should exist after cluster creation"
        
        # Initialize CAPI providers
        capi_config = CAPIProviderConfig(
            kubeconfig_path=kubeconfig_path,
            hetzner_token=hcloud_token,
            clusterctl_path=clusterctl_path
        )
        initializer = CAPIProviderInitializer(capi_config)
        
        result = initializer.initialize_providers()
        assert result is True, "CAPI provider initialization should succeed"
        
        # Verify CAPI provider pods are running
        import subprocess
        import time
        max_wait = 120  # 2 minutes
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-A", "--kubeconfig", str(kubeconfig_path)],
                capture_output=True,
                text=True
            )
            
            # Check for CAPI provider pods
            if all(provider in result.stdout for provider in ["capi-system", "caph-system", "cabpt-system", "cacppt-system"]):
                # Verify all pods are Running or Completed
                lines = result.stdout.split("\n")
                all_ready = True
                for line in lines[1:]:  # Skip header
                    if line.strip() and ("capi-" in line or "caph-" in line or "cabpt-" in line or "cacpt-" in line):
                        parts = line.split()
                        if len(parts) >= 3:
                            status = parts[3]
                            if status not in ["Running", "Completed"]:
                                all_ready = False
                                break
                
                if all_ready:
                    break
            
            time.sleep(5)
        
        # Final verification
        assert "capi-system" in result.stdout, "CAPI core provider should be deployed"
        assert "caph-system" in result.stdout, "CAPH provider should be deployed"
        assert "cabpt-system" in result.stdout, "CABPT provider should be deployed"
        assert "cacppt-system" in result.stdout, "CACPPT provider should be deployed"
        
        # Task 6.2: Apply CAPI manifests
        import pathlib
        fixtures_dir = pathlib.Path(__file__).parent / "fixtures"
        result = initializer.apply_capi_manifests(fixtures_dir)
        assert result is True, "CAPI manifest application should succeed"
        
        # Verify namespace created
        result = subprocess.run(
            ["kubectl", "get", "namespace", "test-cluster-system", "--kubeconfig", str(kubeconfig_path)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, "Test namespace should be created"
        
    finally:
        # Cleanup: Delete Kind cluster
        kind_manager.delete_cluster()
        assert not kind_manager.cluster_exists(), "Kind cluster should be deleted"
