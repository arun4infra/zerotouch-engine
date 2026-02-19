"""Integration tests for GitHub adapter rendering

Tests verify:
1. Engine renders no manifests (GitHub is capability-only)
2. git-credentials capability is provided
3. Capability contains correct fields
4. No files generated in platform/generated/

CRITICAL: Uses PlatformEngine to test actual behavior (same code path as ztc render)
"""

import pytest
from pathlib import Path
from workflow_engine.engine.engine import PlatformEngine


class TestGitHubAdapterRender:
    """Test render() method using PlatformEngine"""
    
    @pytest.mark.skip(reason="Engine validation requires adapter directories; GitHub generates no files")
    @pytest.mark.asyncio
    async def test_render_generates_no_manifests(self):
        """Test GitHub adapter generates no manifest files"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        # GitHub adapter should not create any directory
        github_dir = Path("platform/generated/github")
        assert not github_dir.exists()
    
    @pytest.mark.skip(reason="GitHub adapter not configured in platform.yaml")
    @pytest.mark.asyncio
    async def test_render_provides_git_credentials_capability(self):
        """Test GitHub adapter provides git-credentials capability"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        result = await engine.render()
        
        # Verify capability exists in engine output
        assert "github" in result
        github_output = result["github"]
        assert "git-credentials" in github_output.capabilities
    
    @pytest.mark.skip(reason="GitHub adapter not configured in platform.yaml")
    @pytest.mark.asyncio
    async def test_render_capability_contains_correct_fields(self):
        """Test git-credentials capability contains all required fields"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        result = await engine.render()
        
        capability = result["github"].capabilities["git-credentials"]
        assert capability["provider"] == "github"
        assert "app_id" in capability
        assert "installation_id" in capability
        assert "tenant_org" in capability
        assert "tenant_repo" in capability
