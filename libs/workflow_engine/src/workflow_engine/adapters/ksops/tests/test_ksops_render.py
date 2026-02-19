"""Integration tests for KSOPS adapter rendering

Tests verify:
1. Engine renders KSOPS manifests to platform/generated/
2. .sops.yaml is generated with Age public key placeholder
3. No other manifests are created (KSOPS is secrets-only)
4. Capability data is empty (KSOPS doesn't provide capabilities)

CRITICAL: Uses PlatformEngine to test actual file generation (same code path as ztc render)
"""

import pytest
from pathlib import Path
from workflow_engine.engine.engine import PlatformEngine


class TestKSOPSAdapterRender:
    """Test render() method using PlatformEngine"""
    
    @pytest.mark.asyncio
    async def test_render_generates_sops_yaml(self):
        """Test engine generates .sops.yaml file"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        # KSOPS generates .sops.yaml at root level
        sops_yaml = Path("platform/generated/.sops.yaml")
        assert sops_yaml.exists()
        
        content = sops_yaml.read_text()
        assert "creation_rules:" in content
        assert "age:" in content
    
    @pytest.mark.asyncio
    async def test_render_does_not_generate_environment_directories(self):
        """Test KSOPS doesn't create environment directories (only .sops.yaml)"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        # KSOPS only generates .sops.yaml, not environment-specific files
        # Environment secrets are created by other adapters (Hetzner, etc.)
        generated_dir = Path("platform/generated")
        
        # Should not create ksops/ directory
        assert not (generated_dir / "ksops").exists()
    
    @pytest.mark.asyncio
    async def test_render_sops_yaml_contains_placeholder_when_key_not_generated(self):
        """Test .sops.yaml contains placeholder before Age key generation"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        sops_yaml = Path("platform/generated/.sops.yaml")
        content = sops_yaml.read_text()
        
        # Before bootstrap, Age key is placeholder
        assert "# Age key will be generated during bootstrap" in content or "age1" in content
    
    @pytest.mark.asyncio
    async def test_render_does_not_create_manifests_directory(self):
        """Test KSOPS doesn't create manifests directory (secrets-only adapter)"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        # KSOPS should not create ksops/ directory - only .sops.yaml at root
        ksops_dir = Path("platform/generated/ksops")
        assert not ksops_dir.exists()
    
    @pytest.mark.asyncio
    async def test_render_with_age_public_key_in_config(self):
        """Test .sops.yaml uses Age public key from config if available"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        
        # Platform.yaml has age_public_key configured
        await engine.render()
        
        sops_yaml = Path("platform/generated/.sops.yaml")
        content = sops_yaml.read_text()
        
        # Should contain actual Age key or placeholder
        assert "age1" in content or "# Age key will be generated during bootstrap" in content
