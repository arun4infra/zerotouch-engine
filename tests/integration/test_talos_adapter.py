"""Integration tests for Talos adapter using production code paths

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
from ztc.interfaces.capabilities import KubernetesAPICapability
from pydantic import ValidationError
from ztc.adapters.talos.adapter import TalosConfig, NodeConfig


def test_node_config_validation():
    """Verify NodeConfig validates correctly"""
    valid_node = {
        "name": "cp01-main",
        "ip": "192.168.1.1",
        "role": "controlplane"
    }
    node = NodeConfig(**valid_node)
    assert node.name == "cp01-main"
    assert node.role == "controlplane"


def test_node_config_invalid_name():
    """Verify NodeConfig rejects invalid names"""
    with pytest.raises(ValidationError):
        NodeConfig(name="CP01_MAIN", ip="192.168.1.1", role="controlplane")


def test_talos_config_validation():
    """Verify TalosConfig validates correctly"""
    valid_config = {
        "version": "v1.11.5",
        "factory_image_id": "a" * 64,
        "cluster_name": "production",
        "cluster_endpoint": "192.168.1.1:6443",
        "nodes": [
            {"name": "cp01", "ip": "192.168.1.1", "role": "controlplane"}
        ]
    }
    config = TalosConfig(**valid_config)
    assert config.version == "v1.11.5"
    assert len(config.nodes) == 1


def test_talos_config_invalid_endpoint():
    """Verify TalosConfig rejects invalid endpoint format"""
    with pytest.raises(ValidationError):
        TalosConfig(
            version="v1.11.5",
            factory_image_id="a" * 64,
            cluster_name="test",
            cluster_endpoint="invalid",
            nodes=[]
        )


@pytest.mark.asyncio
async def test_talos_adapter_required_inputs():
    """Verify TalosAdapter returns required inputs via PlatformEngine"""
    temp_dir = tempfile.mkdtemp()
    workspace = Path(temp_dir)
    original_cwd = os.getcwd()
    os.chdir(workspace)
    
    try:
        platform_yaml = workspace / "platform.yaml"
        config = {
            "hetzner": {
                "version": "v1.0.0",
                "api_token": "a" * 64,
                "server_ips": ["192.168.1.1"],
                "rescue_mode_confirm": True
            },
            "cilium": {
                "version": "v1.18.5",
                "bgp": {"enabled": False}
            },
            "talos": {
                "version": "v1.11.5",
                "factory_image_id": "a" * 64,
                "cluster_name": "test",
                "cluster_endpoint": "192.168.1.1:6443",
                "nodes": []
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        engine = PlatformEngine(platform_yaml)
        adapters = engine.resolve_adapters()
        talos_adapter = next(a for a in adapters if a.name == "talos")
        
        inputs = talos_adapter.get_required_inputs()
        assert len(inputs) == 5
        assert inputs[0].name == "version"
        assert inputs[0].default == "v1.11.5"
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_talos_adapter_bootstrap_scripts():
    """Verify TalosAdapter returns bootstrap scripts with context_data via PlatformEngine"""
    temp_dir = tempfile.mkdtemp()
    workspace = Path(temp_dir)
    original_cwd = os.getcwd()
    os.chdir(workspace)
    
    try:
        platform_yaml = workspace / "platform.yaml"
        config = {
            "hetzner": {
                "version": "v1.0.0",
                "api_token": "a" * 64,
                "server_ips": ["192.168.1.1"],
                "rescue_mode_confirm": True
            },
            "cilium": {
                "version": "v1.18.5",
                "bgp": {"enabled": False}
            },
            "talos": {
                "version": "v1.11.5",
                "factory_image_id": "a" * 64,
                "cluster_name": "production",
                "cluster_endpoint": "192.168.1.1:6443",
                "nodes": [
                    {"name": "cp01", "ip": "192.168.1.1", "role": "controlplane"}
                ]
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        engine = PlatformEngine(platform_yaml)
        adapters = engine.resolve_adapters()
        talos_adapter = next(a for a in adapters if a.name == "talos")
        
        scripts = talos_adapter.bootstrap_scripts()
        assert len(scripts) == 4
        assert scripts[0].uri == "talos://bootstrap/embed-network-manifests.sh"
        assert scripts[0].context_data["cluster_name"] == "production"
        assert scripts[1].uri == "talos://bootstrap/install-talos.sh"
        assert "nodes" in scripts[1].context_data
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_talos_adapter_validation_scripts():
    """Verify TalosAdapter returns validation scripts via PlatformEngine"""
    temp_dir = tempfile.mkdtemp()
    workspace = Path(temp_dir)
    original_cwd = os.getcwd()
    os.chdir(workspace)
    
    try:
        platform_yaml = workspace / "platform.yaml"
        config = {
            "hetzner": {
                "version": "v1.0.0",
                "api_token": "a" * 64,
                "server_ips": ["192.168.1.1"],
                "rescue_mode_confirm": True
            },
            "cilium": {
                "version": "v1.18.5",
                "bgp": {"enabled": False}
            },
            "talos": {
                "version": "v1.11.5",
                "factory_image_id": "a" * 64,
                "cluster_name": "test",
                "cluster_endpoint": "192.168.1.1:6443",
                "nodes": [{"name": "cp01", "ip": "192.168.1.1", "role": "controlplane"}]
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        engine = PlatformEngine(platform_yaml)
        adapters = engine.resolve_adapters()
        talos_adapter = next(a for a in adapters if a.name == "talos")
        
        scripts = talos_adapter.validation_scripts()
        assert len(scripts) == 1
        assert scripts[0].uri == "talos://validation/validate-cluster.sh"
        assert scripts[0].context_data["expected_nodes"] == 1
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_talos_adapter_render_single_node():
    """Verify TalosAdapter renders single controlplane node via PlatformEngine"""
    temp_dir = tempfile.mkdtemp()
    workspace = Path(temp_dir)
    original_cwd = os.getcwd()
    os.chdir(workspace)
    
    try:
        platform_yaml = workspace / "platform.yaml"
        config = {
            "hetzner": {
                "version": "v1.0.0",
                "api_token": "a" * 64,
                "server_ips": ["192.168.1.1"],
                "rescue_mode_confirm": True
            },
            "cilium": {
                "version": "v1.18.5",
                "bgp": {"enabled": False}
            },
            "talos": {
                "version": "v1.11.5",
                "factory_image_id": "a" * 64,
                "cluster_name": "test-cluster",
                "cluster_endpoint": "192.168.1.1:6443",
                "nodes": [
                    {"name": "cp01-main", "ip": "192.168.1.1", "role": "controlplane"}
                ]
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        # Verify generated manifests
        generated_dir = Path("platform/generated/talos")
        assert generated_dir.exists()
        assert (generated_dir / "nodes" / "cp01-main" / "config.yaml").exists()
        assert (generated_dir / "talosconfig").exists()
        
        cp_config = (generated_dir / "nodes" / "cp01-main" / "config.yaml").read_text()
        assert "type: controlplane" in cp_config
        assert "test-cluster" in cp_config
        assert "192.168.1.1" in cp_config
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_talos_adapter_render_multi_node():
    """Verify TalosAdapter renders multiple nodes via PlatformEngine"""
    temp_dir = tempfile.mkdtemp()
    workspace = Path(temp_dir)
    original_cwd = os.getcwd()
    os.chdir(workspace)
    
    try:
        platform_yaml = workspace / "platform.yaml"
        config = {
            "hetzner": {
                "version": "v1.0.0",
                "api_token": "a" * 64,
                "server_ips": ["192.168.1.1", "192.168.1.2"],
                "rescue_mode_confirm": True
            },
            "cilium": {
                "version": "v1.18.5",
                "bgp": {"enabled": False}
            },
            "talos": {
                "version": "v1.11.5",
                "factory_image_id": "a" * 64,
                "cluster_name": "prod",
                "cluster_endpoint": "192.168.1.1:6443",
                "nodes": [
                    {"name": "cp01", "ip": "192.168.1.1", "role": "controlplane"},
                    {"name": "worker01", "ip": "192.168.1.2", "role": "worker"}
                ]
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        generated_dir = Path("platform/generated/talos")
        assert (generated_dir / "nodes" / "cp01" / "config.yaml").exists()
        assert (generated_dir / "nodes" / "worker01" / "config.yaml").exists()
        
        worker_config = (generated_dir / "nodes" / "worker01" / "config.yaml").read_text()
        assert "type: worker" in worker_config
        assert "192.168.1.2" in worker_config
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_talos_adapter_capability_validation():
    """Verify TalosAdapter output validates against KubernetesAPICapability via PlatformEngine"""
    temp_dir = tempfile.mkdtemp()
    workspace = Path(temp_dir)
    original_cwd = os.getcwd()
    os.chdir(workspace)
    
    try:
        platform_yaml = workspace / "platform.yaml"
        config = {
            "hetzner": {
                "version": "v1.0.0",
                "api_token": "a" * 64,
                "server_ips": ["192.168.1.1"],
                "rescue_mode_confirm": True
            },
            "cilium": {
                "version": "v1.18.5",
                "bgp": {"enabled": False}
            },
            "talos": {
                "version": "v1.11.5",
                "factory_image_id": "a" * 64,
                "cluster_name": "test",
                "cluster_endpoint": "192.168.1.1:6443",
                "nodes": [
                    {"name": "cp01", "ip": "192.168.1.1", "role": "controlplane"}
                ]
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        capability_data = engine.context.get_capability_data('kubernetes-api')
        assert isinstance(capability_data, KubernetesAPICapability)
        assert capability_data.cluster_endpoint == "192.168.1.1:6443"
        assert capability_data.version == ">=1.28"
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)
