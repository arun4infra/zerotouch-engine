"""Integration tests for Cilium adapter using production code paths

Uses PlatformEngine to create adapters with proper dependency injection.
No direct adapter instantiation per integration testing patterns.
"""

import pytest
from pathlib import Path
import yaml
import tempfile
import shutil
import os

from ztc.engine.engine import PlatformEngine
from ztc.interfaces.capabilities import CNIArtifacts, GatewayAPICapability
from pydantic import ValidationError
from ztc.adapters.cilium.adapter import CiliumConfig, BGPConfig


def test_cilium_config_validation():
    """Verify CiliumConfig validates correctly"""
    valid_config = {
        "version": "v1.18.5",
        "bgp": {
            "enabled": True,
            "asn": 64512
        }
    }
    config = CiliumConfig(**valid_config)
    assert config.version == "v1.18.5"
    assert config.bgp.enabled is True
    assert config.bgp.asn == 64512


def test_cilium_config_bgp_validation():
    """Verify BGPConfig validates ASN range"""
    valid_bgp = BGPConfig(enabled=True, asn=64512)
    assert valid_bgp.asn == 64512
    
    # Invalid ASN should fail
    with pytest.raises(ValidationError):
        BGPConfig(enabled=True, asn=0)


@pytest.mark.asyncio
async def test_cilium_adapter_required_inputs():
    """Verify CiliumAdapter returns required inputs via PlatformEngine"""
    temp_dir = tempfile.mkdtemp()
    workspace = Path(temp_dir)
    original_cwd = os.getcwd()
    os.chdir(workspace)
    
    try:
        # Create platform.yaml with Cilium config
        platform_yaml = workspace / "platform.yaml"
        config = {
            "cilium": {
                "version": "v1.18.5",
                "bgp": {"enabled": False}
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        # Use PlatformEngine to get adapter
        engine = PlatformEngine(platform_yaml)
        adapters = engine.resolve_adapters()
        cilium_adapter = next(a for a in adapters if a.name == "cilium")
        
        inputs = cilium_adapter.get_required_inputs()
        assert len(inputs) == 3
        assert inputs[0].name == "version"
        assert inputs[0].default == "v1.18.5"
        assert inputs[1].name == "bgp_enabled"
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_cilium_adapter_post_work_scripts():
    """Verify CiliumAdapter returns post-work scripts via PlatformEngine"""
    temp_dir = tempfile.mkdtemp()
    workspace = Path(temp_dir)
    original_cwd = os.getcwd()
    os.chdir(workspace)
    
    try:
        platform_yaml = workspace / "platform.yaml"
        config = {
            "cilium": {
                "version": "v1.18.5",
                "bgp": {"enabled": False}
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        engine = PlatformEngine(platform_yaml)
        adapters = engine.resolve_adapters()
        cilium_adapter = next(a for a in adapters if a.name == "cilium")
        
        scripts = cilium_adapter.post_work_scripts()
        assert len(scripts) == 2
        assert scripts[0].uri == "cilium://post_work/wait-cilium.sh"
        assert scripts[1].uri == "cilium://post_work/wait-gateway-api.sh"
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_cilium_adapter_validation_scripts():
    """Verify CiliumAdapter returns validation scripts via PlatformEngine"""
    temp_dir = tempfile.mkdtemp()
    workspace = Path(temp_dir)
    original_cwd = os.getcwd()
    os.chdir(workspace)
    
    try:
        platform_yaml = workspace / "platform.yaml"
        config = {
            "cilium": {
                "version": "v1.18.5",
                "bgp": {"enabled": False}
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        engine = PlatformEngine(platform_yaml)
        adapters = engine.resolve_adapters()
        cilium_adapter = next(a for a in adapters if a.name == "cilium")
        
        scripts = cilium_adapter.validation_scripts()
        assert len(scripts) == 1
        assert scripts[0].uri == "cilium://validation/validate-cni.sh"
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_cilium_adapter_get_invalid_fields():
    """Verify get_invalid_fields detects OS changes via PlatformEngine"""
    temp_dir = tempfile.mkdtemp()
    workspace = Path(temp_dir)
    original_cwd = os.getcwd()
    os.chdir(workspace)
    
    try:
        platform_yaml = workspace / "platform.yaml"
        config = {
            "cilium": {
                "version": "v1.18.5",
                "bgp": {"enabled": False}
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        engine = PlatformEngine(platform_yaml)
        adapters = engine.resolve_adapters()
        cilium_adapter = next(a for a in adapters if a.name == "cilium")
        
        # No invalid fields when OS is talos
        current_config = {"embedded_mode": True}
        platform_context = {"os": "talos"}
        invalid = cilium_adapter.get_invalid_fields(current_config, platform_context)
        assert len(invalid) == 0
        
        # embedded_mode invalid when OS changes
        platform_context = {"os": "ubuntu"}
        invalid = cilium_adapter.get_invalid_fields(current_config, platform_context)
        assert "embedded_mode" in invalid
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_cilium_adapter_render():
    """Verify CiliumAdapter render generates manifests via PlatformEngine"""
    temp_dir = tempfile.mkdtemp()
    workspace = Path(temp_dir)
    original_cwd = os.getcwd()
    os.chdir(workspace)
    
    try:
        platform_yaml = workspace / "platform.yaml"
        config = {
            "cilium": {
                "version": "v1.18.5",
                "bgp": {
                    "enabled": True,
                    "asn": 64512
                }
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        # Verify generated manifests
        generated_dir = Path("platform/generated/cilium")
        assert generated_dir.exists()
        assert (generated_dir / "manifests.yaml").exists()
        
        manifest_content = (generated_dir / "manifests.yaml").read_text()
        assert "v1.18.5" in manifest_content
        assert "bgp-enabled: \"true\"" in manifest_content
        assert "bgp-asn: \"64512\"" in manifest_content
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_cilium_adapter_render_no_bgp():
    """Verify CiliumAdapter render without BGP via PlatformEngine"""
    temp_dir = tempfile.mkdtemp()
    workspace = Path(temp_dir)
    original_cwd = os.getcwd()
    os.chdir(workspace)
    
    try:
        platform_yaml = workspace / "platform.yaml"
        config = {
            "cilium": {
                "version": "v1.18.5",
                "bgp": {"enabled": False}
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        generated_dir = Path("platform/generated/cilium")
        manifest_content = (generated_dir / "manifests.yaml").read_text()
        assert "bgp-enabled: \"false\"" in manifest_content
        assert "bgp-asn" not in manifest_content
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_cilium_adapter_capability_validation():
    """Verify CiliumAdapter output validates against capability models via PlatformEngine"""
    temp_dir = tempfile.mkdtemp()
    workspace = Path(temp_dir)
    original_cwd = os.getcwd()
    os.chdir(workspace)
    
    try:
        platform_yaml = workspace / "platform.yaml"
        config = {
            "cilium": {
                "version": "v1.18.5",
                "bgp": {"enabled": False}
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        engine = PlatformEngine(platform_yaml)
        adapters = engine.resolve_adapters()
        cilium_adapter = next(a for a in adapters if a.name == "cilium")
        
        # Render through engine to get capability data
        await engine.render()
        
        # Get capability data from context
        cni_data = engine.context.get_capability_data('cni')
        assert isinstance(cni_data, CNIArtifacts)
        assert cni_data.manifests is not None
        assert cni_data.ready is False
        
        gateway_data = engine.context.get_capability_data('gateway-api')
        assert isinstance(gateway_data, GatewayAPICapability)
        assert gateway_data.version == "v1.18.5"
        assert gateway_data.crds_embedded is True
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)
