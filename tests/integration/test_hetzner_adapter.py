"""Integration tests for Hetzner adapter using production code paths

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
from ztc.interfaces.capabilities import CloudInfrastructureCapability
from pydantic import ValidationError
from ztc.adapters.hetzner.adapter import HetznerConfig


def test_hetzner_config_validation():
    """Verify HetznerConfig validates correctly"""
    valid_config = {
        "version": "v1.0.0",
        "api_token": "a" * 64,
        "server_ips": ["192.168.1.1"],
        "rescue_mode_confirm": True
    }
    config = HetznerConfig(**valid_config)
    assert config.api_token == "a" * 64
    assert len(config.server_ips) == 1


def test_hetzner_config_invalid_token():
    """Verify HetznerConfig rejects invalid token length"""
    invalid_config = {
        "version": "v1.0.0",
        "api_token": "short",
        "server_ips": ["192.168.1.1"],
        "rescue_mode_confirm": True
    }
    with pytest.raises(ValidationError):
        HetznerConfig(**invalid_config)


@pytest.mark.asyncio
async def test_hetzner_adapter_required_inputs():
    """Verify HetznerAdapter returns required inputs via PlatformEngine"""
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
                "rescue_mode_confirm": False
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        engine = PlatformEngine(platform_yaml)
        adapters = engine.resolve_adapters()
        hetzner_adapter = next(a for a in adapters if a.name == "hetzner")
        
        inputs = hetzner_adapter.get_required_inputs()
        assert len(inputs) == 4
        assert inputs[0].name == "version"
        assert inputs[1].name == "api_token"
        assert inputs[1].type == "password"
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_hetzner_adapter_pre_work_scripts():
    """Verify HetznerAdapter returns pre-work scripts via PlatformEngine"""
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
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        engine = PlatformEngine(platform_yaml)
        adapters = engine.resolve_adapters()
        hetzner_adapter = next(a for a in adapters if a.name == "hetzner")
        
        scripts = hetzner_adapter.pre_work_scripts()
        assert len(scripts) == 0  # Hetzner has no pre-work scripts
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_hetzner_adapter_validation_scripts():
    """Verify HetznerAdapter returns validation scripts via PlatformEngine"""
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
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        engine = PlatformEngine(platform_yaml)
        adapters = engine.resolve_adapters()
        hetzner_adapter = next(a for a in adapters if a.name == "hetzner")
        
        scripts = hetzner_adapter.validation_scripts()
        assert len(scripts) == 0  # Hetzner has no validation scripts (uses Python API)
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_hetzner_adapter_render():
    """Verify HetznerAdapter render generates correct output via PlatformEngine"""
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
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        # Get capability data from context
        capability_data = engine.context.get_capability_data('cloud-infrastructure')
        assert isinstance(capability_data, CloudInfrastructureCapability)
        assert capability_data.provider == "hetzner"
        assert len(capability_data.server_ids) == 2
        assert capability_data.rescue_mode_enabled is True
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_hetzner_adapter_capability_validation():
    """Verify HetznerAdapter output validates against CloudInfrastructureCapability via PlatformEngine"""
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
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        capability_data = engine.context.get_capability_data('cloud-infrastructure')
        assert isinstance(capability_data, CloudInfrastructureCapability)
        assert capability_data.provider == "hetzner"
        assert capability_data.rescue_mode_enabled is True
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)
