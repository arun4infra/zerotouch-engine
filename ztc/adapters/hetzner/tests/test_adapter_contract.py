"""Unit tests for Hetzner adapter contract validation

Tests verify:
1. Hetzner adapter follows capability contract
2. HetznerAdapter implements all abstract methods
3. Hetzner provides cloud-infrastructure capability
"""

import pytest
from pydantic import ValidationError
from ztc.adapters.base import PlatformAdapter
from ztc.adapters.hetzner.adapter import HetznerAdapter, HetznerConfig


class TestHetznerAdapterContract:
    """Test Hetzner adapter follows PlatformAdapter contract"""
    
    def test_hetzner_adapter_has_config_model(self):
        """Verify HetznerAdapter defines config_model property"""
        adapter = HetznerAdapter({})
        assert adapter.config_model == HetznerConfig
    
    def test_hetzner_adapter_implements_required_methods(self):
        """Verify HetznerAdapter implements all abstract methods"""
        required_methods = [
            "get_required_inputs",
            "pre_work_scripts",
            "bootstrap_scripts",
            "post_work_scripts",
            "validation_scripts",
            "render",
        ]
        
        for method_name in required_methods:
            assert hasattr(HetznerAdapter, method_name), (
                f"HetznerAdapter missing required method: {method_name}"
            )


class TestHetznerCapabilityContract:
    """Test Hetzner adapter capability contracts"""
    
    def test_hetzner_provides_cloud_infrastructure_capability(self):
        """Test Hetzner adapter provides cloud-infrastructure capability"""
        metadata = HetznerAdapter({}).load_metadata()
        provides = [cap["capability"] for cap in metadata.get("provides", [])]
        assert "cloud-infrastructure" in provides
    
    def test_hetzner_requires_no_capabilities(self):
        """Test Hetzner adapter has no capability requirements"""
        metadata = HetznerAdapter({}).load_metadata()
        requires = metadata.get("requires", [])
        assert len(requires) == 0


class TestHetznerConfigValidation:
    """Test HetznerConfig Pydantic model validation"""
    
    def test_hetzner_config_validates_api_token_length(self):
        """Test HetznerConfig validates API token is 64 characters"""
        valid_data = {
            "version": "v1.0.0",
            "api_token": "a" * 64,
            "server_ips": ["192.168.1.1"],
            "rescue_mode_confirm": False
        }
        config = HetznerConfig(**valid_data)
        assert len(config.api_token) == 64
        
        with pytest.raises(ValidationError):
            HetznerConfig(**{**valid_data, "api_token": "short"})
    
    def test_hetzner_config_validates_server_ips(self):
        """Test HetznerConfig validates server_ips list"""
        valid_data = {
            "version": "v1.0.0",
            "api_token": "a" * 64,
            "server_ips": ["192.168.1.1", "192.168.1.2"],
            "rescue_mode_confirm": False
        }
        config = HetznerConfig(**valid_data)
        assert len(config.server_ips) == 2
        
        with pytest.raises(ValidationError):
            HetznerConfig(**{**valid_data, "server_ips": None})
