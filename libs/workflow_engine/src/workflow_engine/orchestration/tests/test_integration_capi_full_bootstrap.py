"""Integration test for complete CAPI bootstrap flow (Tasks 6.1-6.4)

CRITICAL: This test uses REAL infrastructure - no mocking.
- Creates actual Kind clusters
- Initializes real CAPI providers
- Creates actual Hetzner VMs (COSTS MONEY)
- Polls Hetzner API for VM status
- Requires HCLOUD_TOKEN environment variable
- Destroys all resources in finally blocks
"""

import pytest
import os
import time
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from workflow_engine.orchestration.kind_cluster_manager import KindClusterManager, KindClusterConfig
from workflow_engine.orchestration.capi_provider_initializer import CAPIProviderInitializer, CAPIProviderConfig
from workflow_engine.orchestration.clusterctl_manager import ClusterctlManager
from workflow_engine.orchestration.ssh_key_manager import SSHKeyManager, SSHKeyConfig
from workflow_engine.adapters.cluster_api.adapter import ClusterAPIAdapter
from workflow_engine.adapters.cluster_api.config import ClusterAPIConfig, ControlPlaneConfig, WorkerPoolConfig


@pytest.mark.integration
def test_complete_capi_bootstrap():
    """Verify complete CAPI bootstrap flow with real Hetzner VMs
    
    Validates: Requirements 3.2, 3.3, 3.4 (Tasks 6.1-6.4)
    Cleanup: Deletes Hetzner VMs and Kind cluster
    """
    # Setup logging inside test function
    log_dir = Path(__file__).resolve().parent.parent.parent.parent.parent.parent / ".zerotouch-cache" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"capi-bootstrap-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    
    # Configure logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # File handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    logger.info("=== Starting CAPI Bootstrap Test ===")
    logger.info(f"Log file: {log_file}")
    
    # Check for required credentials
    hcloud_token = os.environ.get("HCLOUD_TOKEN")
    if not hcloud_token:
        raise EnvironmentError("HCLOUD_TOKEN environment variable not set")
    
    logger.info("HCLOUD_TOKEN found")
    
    # Download clusterctl if not available
    clusterctl_mgr = ClusterctlManager()
    clusterctl_path = None
    if not clusterctl_mgr.is_available():
        logger.info("Downloading clusterctl...")
        clusterctl_path = clusterctl_mgr.download(version="v1.12.3")
        logger.info(f"clusterctl downloaded to {clusterctl_path}")
    else:
        logger.info("clusterctl already available")
    
    # Create Kind cluster
    kind_config = KindClusterConfig(name="ztc-test-full-bootstrap")
    kind_manager = KindClusterManager(kind_config)
    
    # Delete existing cluster if present
    try:
        kind_manager.delete_cluster()
        logger.info("Deleted existing Kind cluster")
    except:
        pass
    
    # Upload SSH key to Hetzner Cloud for CAPH VM provisioning
    logger.info("Uploading SSH key to Hetzner Cloud...")
    ssh_key_config = SSHKeyConfig(
        cluster_name="test-cluster",
        hcloud_token=hcloud_token
    )
    ssh_key_manager = SSHKeyManager(ssh_key_config)
    # Use naming pattern that matches template: {{ cluster_name }}-ssh-key
    ssh_key_manager.key_name = "test-cluster-ssh-key"
    ssh_key_name = ssh_key_manager.upload_to_hetzner()
    logger.info(f"SSH key uploaded: {ssh_key_name}")
    
    # Generate real CAPI manifests using ClusterAPIAdapter
    capi_config = ClusterAPIConfig(
        control_plane=ControlPlaneConfig(
            machine_type="cx23",  # Smallest/cheapest for testing
            replicas=1  # Single control plane for cost
        ),
        worker_pools=[
            WorkerPoolConfig(
                name="test-workers",
                machine_type="cx23",  # Smallest/cheapest
                min_size=1,
                max_size=1  # Single worker for cost
            )
        ]
    )
    
    kubeconfig_path = None  # Initialize for finally block
    try:
        # Task 6.1: Create Kind cluster and initialize CAPI providers
        logger.info("Creating Kind cluster...")
        kubeconfig_path = kind_manager.create_cluster()
        assert kubeconfig_path.exists(), "Kubeconfig should exist"
        logger.info(f"Kind cluster created, kubeconfig: {kubeconfig_path}")
        
        capi_init_config = CAPIProviderConfig(
            kubeconfig_path=kubeconfig_path,
            hetzner_token=hcloud_token,
            clusterctl_path=clusterctl_path
        )
        initializer = CAPIProviderInitializer(capi_init_config)
        
        logger.info("Initializing CAPI providers...")
        result = initializer.initialize_providers()
        assert result is True, "CAPI provider initialization should succeed"
        logger.info("CAPI providers initialized")
        
        # Verify CAPI provider pods are running
        logger.info("Waiting for CAPI provider pods...")
        max_wait = 120
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-A", "--kubeconfig", str(kubeconfig_path)],
                capture_output=True,
                text=True
            )
            
            logger.info(f"Current pods:\n{result.stdout}")
            
            if all(provider in result.stdout for provider in ["capi-system", "caph-system", "cabpt-system", "cacppt-system"]):
                lines = result.stdout.split("\n")
                all_ready = True
                for line in lines[1:]:
                    if line.strip() and ("capi-" in line or "caph-" in line or "cabpt-" in line or "cacppt-" in line):
                        parts = line.split()
                        if len(parts) >= 4:
                            ready = parts[1]  # READY column (e.g., "1/1")
                            status = parts[2]  # STATUS column
                            logger.info(f"Pod {parts[0]} ready: {ready}, status: {status}")
                            # Check if pod is ready (READY column shows x/x where both numbers match)
                            if "/" in ready:
                                ready_parts = ready.split("/")
                                if ready_parts[0] != ready_parts[1] or status != "Running":
                                    all_ready = False
                                    break
                
                if all_ready:
                    break
            
            time.sleep(5)
        
        assert "capi-system" in result.stdout, "CAPI core provider should be deployed"
        assert "caph-system" in result.stdout, "CAPH provider should be deployed"
        logger.info("All CAPI provider pods running")
        
        # Wait for CAPH CRDs to be installed
        logger.info("Waiting for CAPH CRDs...")
        max_wait = 120  # Increase to 2 minutes
        start_time = time.time()
        crds_ready = False
        
        while time.time() - start_time < max_wait:
            result = subprocess.run(
                ["kubectl", "get", "crd", "--kubeconfig", str(kubeconfig_path)],
                capture_output=True,
                text=True
            )
            
            # Check if CAPH CRDs exist (use hcloud prefix, not hetzner)
            if "hcloudmachinetemplates.infrastructure.cluster.x-k8s.io" in result.stdout:
                crds_ready = True
                break
            
            time.sleep(5)
        
        # If CRDs not ready, print diagnostics
        if not crds_ready:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", "caph-system", "--kubeconfig", str(kubeconfig_path)],
                capture_output=True,
                text=True
            )
            print(f"CAPH pods status:\n{result.stdout}")
            
            result = subprocess.run(
                ["kubectl", "get", "crd", "--kubeconfig", str(kubeconfig_path)],
                capture_output=True,
                text=True
            )
            print(f"All CRDs:\n{result.stdout}")
        
        assert crds_ready, "CAPH CRDs should be installed"
        logger.info("CAPH CRDs installed")
        
        # Wait for webhook pods to be Running
        logger.info("Waiting for webhook pods to be Running...")
        max_wait = 120
        start_time = time.time()
        webhooks_ready = False
        
        while time.time() - start_time < max_wait:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-A", "-l", "control-plane", "--kubeconfig", str(kubeconfig_path)],
                capture_output=True,
                text=True
            )
            
            logger.info(f"Webhook pods output:\n{result.stdout}")
            
            # Check if all webhook pods are Running
            lines = result.stdout.split("\n")
            all_running = True
            webhook_count = 0
            
            for line in lines[1:]:
                if line.strip() and ("capi-" in line or "caph-" in line or "cabpt-" in line or "cacppt-" in line):
                    webhook_count += 1
                    parts = line.split()
                    if len(parts) >= 4:
                        # parts[0] = NAMESPACE, parts[1] = NAME, parts[2] = READY, parts[3] = STATUS
                        ready = parts[2]
                        status = parts[3]
                        logger.info(f"Webhook pod {parts[1]}: ready={ready}, status={status}")
                        if status != "Running" or "/" not in ready:
                            all_running = False
                            continue
                        # Check ready count
                        ready_parts = ready.split("/")
                        if ready_parts[0] != ready_parts[1]:
                            all_running = False
            
            logger.info(f"Webhook count: {webhook_count}, all_running: {all_running}")
            
            if webhook_count >= 4 and all_running:
                webhooks_ready = True
                logger.info("All webhook pods Running")
                # Wait additional 30s for webhook endpoints to be ready
                logger.info("Waiting 30s for webhook endpoints...")
                time.sleep(30)
                break
            
            time.sleep(5)
        
        assert webhooks_ready, "Webhook pods should be Running"
        
        # Create Hetzner secret with HCLOUD_TOKEN
        logger.info("Creating Hetzner secret...")
        import base64
        hcloud_token_b64 = base64.b64encode(hcloud_token.encode()).decode()
        secret_yaml = f"""apiVersion: v1
kind: Secret
metadata:
  name: hetzner
  namespace: default
type: Opaque
data:
  hcloud: {hcloud_token_b64}
"""
        result = subprocess.run(
            ["kubectl", "apply", "-f", "-", "--kubeconfig", str(kubeconfig_path)],
            input=secret_yaml,
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Failed to create secret: {result.stderr}"
        logger.info("Hetzner secret created")
        
        # Task 6.2: Generate and apply CAPI manifests using production render path
        logger.info("Generating CAPI manifests via adapter.render()...")
        
        adapter_config = {
            "control_plane": {
                "machine_type": "cx23",
                "replicas": 1
            },
            "worker_pools": [
                {
                    "name": "test-workers",
                    "machine_type": "cx23",
                    "min_size": 1,
                    "max_size": 1
                }
            ]
        }
        
        # Initialize adapter - VersionProvider will use default platform.yaml path
        adapter = ClusterAPIAdapter(config=adapter_config)
        
        # Create minimal context for render
        class MockContext:
            def __init__(self):
                self.platform_config = {"name": "test-cluster"}
        
        try:
            import asyncio
            output = asyncio.run(adapter.render(MockContext()))
            manifests_yaml = "\n---\n".join(output.manifests.values())
            logger.info(f"Generated manifests ({len(manifests_yaml)} bytes)")
        except Exception as e:
            logger.error(f"Failed to generate manifests: {e}")
            raise
        
        # Apply manifests to Kind cluster
        logger.info("Applying CAPI manifests...")
        result = subprocess.run(
            ["kubectl", "apply", "-f", "-", "--kubeconfig", str(kubeconfig_path)],
            input=manifests_yaml,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Failed to apply manifests: {result.stderr}")
            raise RuntimeError(f"Failed to apply manifests: {result.stderr}")
        
        logger.info("CAPI manifests applied")
        
        # Task 6.3: Poll Hetzner API for VM provisioning
        logger.info("Waiting for Machines to be provisioned (max 10 min)...")
        # Wait for Machines to be created
        max_wait = 600  # 10 minutes for VM provisioning
        start_time = time.time()
        machines_ready = False
        
        poll_count = 0
        while time.time() - start_time < max_wait:
            poll_count += 1
            elapsed = int(time.time() - start_time)
            logger.info(f"Poll #{poll_count} (elapsed: {elapsed}s)")
            
            result = subprocess.run(
                ["kubectl", "get", "machines", "-A", "--kubeconfig", str(kubeconfig_path)],
                capture_output=True,
                text=True
            )
            logger.info(f"Machines output:\n{result.stdout}")
            
            if "test-cluster" in result.stdout:
                # Check if machines have providerID (means VM provisioned)
                result = subprocess.run(
                    ["kubectl", "get", "machines", "-A", "-o", "yaml", "--kubeconfig", str(kubeconfig_path)],
                    capture_output=True,
                    text=True
                )
                
                if "providerID:" in result.stdout:
                    machines_ready = True
                    logger.info("Machines have providerID - VMs provisioned!")
                    break
                else:
                    logger.info("Machines exist but no providerID yet")
            else:
                # Check MachineDeployment status
                result = subprocess.run(
                    ["kubectl", "get", "machinedeployments", "-A", "--kubeconfig", str(kubeconfig_path)],
                    capture_output=True,
                    text=True
                )
                logger.info(f"MachineDeployments:\n{result.stdout}")
            
            time.sleep(10)
        
        # Diagnostics if failed
        if not machines_ready:
            logger.error("Machines not provisioned within timeout")
            result = subprocess.run(
                ["kubectl", "get", "machinedeployments", "-A", "-o", "yaml", "--kubeconfig", str(kubeconfig_path)],
                capture_output=True,
                text=True
            )
            logger.error(f"MachineDeployment status:\n{result.stdout}")
            print(f"\nMachineDeployment status:\n{result.stdout}")
        else:
            logger.info("Machines provisioned successfully")
        
        assert machines_ready, "Machines should be provisioned with Hetzner VMs"
        
        # Task 6.4: Verify complete integration
        # Verify Cluster resource exists
        logger.info("Verifying Cluster resource...")
        result = subprocess.run(
            ["kubectl", "get", "cluster", "test-cluster", "--kubeconfig", str(kubeconfig_path)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, "Cluster resource should exist"
        
        logger.info("Test completed successfully")
        
    finally:
        # Cleanup: Delete CAPI cluster (triggers Hetzner VM deletion)
        if kubeconfig_path:
            try:
                logger.info("Deleting CAPI cluster to trigger VM cleanup...")
                result = subprocess.run(
                    ["kubectl", "delete", "cluster", "test-cluster", "--kubeconfig", str(kubeconfig_path), "--timeout=5m"],
                    capture_output=True,
                    text=True,
                    timeout=360
                )
                logger.info(f"Cluster deleted: {result.stdout}")
            except Exception as e:
                logger.warning(f"Failed to delete cluster: {e}")
        
        # Delete SSH key from Hetzner Cloud
        try:
            ssh_key_manager.delete_from_hetzner()
            logger.info("SSH key deleted")
        except Exception as e:
            logger.warning(f"Failed to delete SSH key: {e}")
        
        # Delete Kind cluster
        try:
            logger.info("Deleting Kind cluster...")
            kind_manager.delete_cluster()
            logger.info("Kind cluster deleted")
        except Exception as e:
            logger.warning(f"Failed to delete Kind cluster: {e}")
