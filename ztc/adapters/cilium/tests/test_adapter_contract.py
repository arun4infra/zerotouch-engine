"""Unit tests for Cilium adapter contract validation

Tests verify:
1. Cilium adapter follows capability contract
2. CiliumAdapter implements all abstract methods
3. Cilium provides CNI and Gateway API capabilities
"""

import pytest
from pydantic import ValidationError
from ztc.adapters.base import PlatformAdapter, ScriptReference
from ztc.adapters.cilium.adapter import CiliumAdapter, CiliumConfig, CiliumScripts


class TestCiliumAdapterContract:
    """Test Cilium adapter follows PlatformAdapter contract"""
    
    def test_cilium_adapter_has_config_model(self):
        """Verify CiliumAdapter defines config_model property"""
        adapter = CiliumAdapter({})
        assert adapter.config_model == CiliumConfig
    
    def test_cilium_adapter_implements_required_methods(self):
        """Verify CiliumAdapter implements all abstract methods"""
        required_methods = [
            "get_required_inputs",
            "pre_work_scripts",
            "bootstrap_scripts",
            "post_work_scripts",
            "validation_scripts",
            "render",
        ]
        
        for method_name in required_methods:
            assert hasattr(CiliumAdapter, method_name), (
                f"CiliumAdapter missing required method: {method_name}"
            )


class TestCiliumScriptValidation:
    """Test CiliumScripts enum validates script existence following standard pattern"""
    
    def test_post_work_scripts_exist(self):
        """Test post_work/ scripts exist in correct subdirectory"""
        ref = ScriptReference(
            package="ztc.adapters.cilium.scripts",
            resource=CiliumScripts.WAIT_CILIUM,
            description="Wait for Cilium CNI"
        )
        assert ref.uri == "cilium://post_work/wait-cilium.sh"
    
    def test_validation_scripts_exist(self):
        """Test validation/ scripts exist in correct subdirectory"""
        ref = ScriptReference(
            package="ztc.adapters.cilium.scripts",
            resource=CiliumScripts.VALIDATE_CNI,
            description="Validate CNI"
        )
        assert ref.uri == "cilium://validation/validate-cni.sh"


class TestCiliumCapabilityContract:
    """Test Cilium adapter capability contracts"""
    
    def test_cilium_provides_cni_capability(self):
        """Test Cilium adapter provides cni capability"""
        metadata = CiliumAdapter({}).load_metadata()
        provides = [cap["capability"] for cap in metadata.get("provides", [])]
        assert "cni" in provides
    
    def test_cilium_provides_gateway_api_capability(self):
        """Test Cilium adapter provides gateway-api capability"""
        metadata = CiliumAdapter({}).load_metadata()
        provides = [cap["capability"] for cap in metadata.get("provides", [])]
        assert "gateway-api" in provides
    
    def test_cilium_requires_kubernetes_api_capability(self):
        """Test Cilium adapter requires kubernetes-api capability"""
        metadata = CiliumAdapter({}).load_metadata()
        requires = [cap["capability"] for cap in metadata.get("requires", [])]
        assert "kubernetes-api" in requires


class TestCiliumConfigValidation:
    """Test CiliumConfig Pydantic model validation"""
    
    def test_cilium_config_validates_version(self):
        """Test CiliumConfig validates version"""
        valid_data = {
            "version": "v1.18.5",
            "bgp": {"enabled": False}
        }
        config = CiliumConfig(**valid_data)
        assert config.version == "v1.18.5"
    
    def test_cilium_config_validates_bgp_asn(self):
        """Test CiliumConfig validates BGP ASN range"""
        valid_data = {
            "version": "v1.18.5",
            "bgp": {"enabled": True, "asn": 64512}
        }
        config = CiliumConfig(**valid_data)
        assert config.bgp.asn == 64512
        
        with pytest.raises(ValidationError):
            CiliumConfig(**{
                "version": "v1.18.5",
                "bgp": {"enabled": True, "asn": 5000000000}
            })
