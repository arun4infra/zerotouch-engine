"""Unit tests for Talos adapter contract validation

Tests verify:
1. Talos adapter follows capability contract
2. TalosAdapter implements all abstract methods
3. TalosScripts enum validates script existence
"""

import pytest
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, ValidationError
from ztc.interfaces.capabilities import (
    Capability,
    CAPABILITY_CONTRACTS,
    KubernetesAPICapability,
)
from ztc.adapters.base import (
    PlatformAdapter,
    ScriptReference,
    InputPrompt,
    AdapterOutput,
)
from ztc.adapters.talos.adapter import TalosAdapter, TalosConfig, TalosScripts


class TestTalosAdapterContract:
    """Test Talos adapter follows PlatformAdapter contract"""
    
    def test_talos_adapter_has_config_model(self):
        """Verify TalosAdapter defines config_model property"""
        adapter = TalosAdapter({})
        assert adapter.config_model == TalosConfig
    
    def test_talos_adapter_implements_required_methods(self):
        """Verify TalosAdapter implements all abstract methods"""
        required_methods = [
            "get_required_inputs",
            "pre_work_scripts",
            "bootstrap_scripts",
            "post_work_scripts",
            "validation_scripts",
            "render",
        ]
        
        for method_name in required_methods:
            assert hasattr(TalosAdapter, method_name), (
                f"TalosAdapter missing required method: {method_name}"
            )


class TestTalosScriptValidation:
    """Test TalosScripts enum validates script existence following standard pattern"""
    
    def test_pre_work_scripts_exist(self):
        """Test pre_work/ scripts exist in correct subdirectory"""
        ref = ScriptReference(
            package="ztc.adapters.talos.scripts",
            resource=TalosScripts.ENABLE_RESCUE,
            description="Enable rescue mode"
        )
        assert ref.uri == "talos://pre_work/enable-rescue-mode.sh"
    
    def test_bootstrap_scripts_exist(self):
        """Test bootstrap/ scripts exist in correct subdirectory"""
        ref = ScriptReference(
            package="ztc.adapters.talos.scripts",
            resource=TalosScripts.INSTALL,
            description="Install Talos OS"
        )
        assert ref.uri == "talos://bootstrap/install-talos.sh"
    
    def test_validation_scripts_exist(self):
        """Test validation/ scripts exist in correct subdirectory"""
        ref = ScriptReference(
            package="ztc.adapters.talos.scripts",
            resource=TalosScripts.VALIDATE_CLUSTER,
            description="Validate cluster"
        )
        assert ref.uri == "talos://validation/validate-cluster.sh"
    
    def test_script_reference_with_context_data(self):
        """Test ScriptReference accepts context_data"""
        ref = ScriptReference(
            package="ztc.adapters.talos.scripts",
            resource=TalosScripts.BOOTSTRAP,
            description="Bootstrap Talos cluster",
            context_data={
                "server_ip": "192.168.1.1",
                "controlplane_ip": "192.168.1.10",
                "talosconfig_path": "/tmp/talosconfig"
            }
        )
        assert ref.context_data["server_ip"] == "192.168.1.1"


class TestTalosCapabilityContract:
    """Test Talos adapter capability contracts"""
    
    def test_talos_provides_kubernetes_api_capability(self):
        """Test Talos adapter provides kubernetes-api capability"""
        metadata = TalosAdapter({}).load_metadata()
        provides = [cap["capability"] for cap in metadata.get("provides", [])]
        assert "kubernetes-api" in provides
    
    def test_talos_requires_cloud_infrastructure_capability(self):
        """Test Talos adapter requires cloud-infrastructure capability"""
        metadata = TalosAdapter({}).load_metadata()
        requires = [cap["capability"] for cap in metadata.get("requires", [])]
        assert "cloud-infrastructure" in requires
    
    def test_talos_requires_cni_capability(self):
        """Test Talos adapter requires cni capability"""
        metadata = TalosAdapter({}).load_metadata()
        requires = [cap["capability"] for cap in metadata.get("requires", [])]
        assert "cni" in requires


class TestTalosConfigValidation:
    """Test TalosConfig Pydantic model validation"""
    
    def test_talos_config_validates_cluster_endpoint(self):
        """Test TalosConfig validates cluster_endpoint format"""
        valid_data = {
            "version": "v1.11.5",
            "factory_image_id": "a" * 64,
            "cluster_name": "test-cluster",
            "cluster_endpoint": "192.168.1.10:6443",
            "nodes": [
                {"name": "cp01", "ip": "192.168.1.10", "role": "controlplane"}
            ]
        }
        config = TalosConfig(**valid_data)
        assert config.cluster_endpoint == "192.168.1.10:6443"
        
        with pytest.raises(ValidationError):
            TalosConfig(**{**valid_data, "cluster_endpoint": "invalid"})
    
    def test_talos_config_validates_node_structure(self):
        """Test TalosConfig validates node configuration"""
        valid_data = {
            "version": "v1.11.5",
            "factory_image_id": "a" * 64,
            "cluster_name": "test-cluster",
            "cluster_endpoint": "192.168.1.10:6443",
            "nodes": [
                {"name": "cp01", "ip": "192.168.1.10", "role": "controlplane"}
            ]
        }
        config = TalosConfig(**valid_data)
        assert len(config.nodes) == 1
        assert config.nodes[0].role == "controlplane"
