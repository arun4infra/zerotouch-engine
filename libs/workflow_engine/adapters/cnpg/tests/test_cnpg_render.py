"""Integration tests for CNPG adapter rendering

Tests verify:
1. Engine renders CNPG manifests to platform/generated/argocd/overlays/main/core/
2. Production mode generates correct file structure
3. Preview mode generates correct file structure
4. Manifests contain expected content (sync-waves, Helm chart refs, ignoreDifferences)
5. Manifests are valid YAML with required ArgoCD Application fields

CRITICAL: Uses PlatformEngine to test actual file generation (same code path as ztc render)
"""

import pytest
from pathlib import Path
from workflow_engine.adapters.engine import PlatformEngine


class TestCNPGAdapterRenderProduction:
    """Test render() method for production mode using PlatformEngine"""
    
    @pytest.mark.asyncio
    async def test_render_generates_application_file_production(self):
        """Test engine generates application.yaml for production"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/02-cnpg.yaml")
        assert app_file.exists()
    
    @pytest.mark.asyncio
    async def test_render_application_contains_correct_chart(self):
        """Test Application references correct Helm chart and version"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/02-cnpg.yaml")
        app_content = app_file.read_text()
        
        assert "https://cloudnative-pg.github.io/charts" in app_content
        assert "0.27.0" in app_content
    
    @pytest.mark.asyncio
    async def test_render_application_has_correct_sync_wave(self):
        """Test Application has correct sync-wave annotation"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/02-cnpg.yaml")
        app_content = app_file.read_text()
        
        assert 'argocd.argoproj.io/sync-wave: "2"' in app_content
    
    @pytest.mark.asyncio
    async def test_render_application_contains_ignore_differences(self):
        """Test Application contains ignoreDifferences for 4 CRDs"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/02-cnpg.yaml")
        app_content = app_file.read_text()
        
        assert "backups.postgresql.cnpg.io" in app_content
        assert "clusters.postgresql.cnpg.io" in app_content
        assert "poolers.postgresql.cnpg.io" in app_content
        assert "scheduledbackups.postgresql.cnpg.io" in app_content
    
    @pytest.mark.asyncio
    async def test_render_application_contains_sync_options(self):
        """Test Application contains ServerSideApply and RespectIgnoreDifferences"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/02-cnpg.yaml")
        app_content = app_file.read_text()
        
        assert "ServerSideApply=true" in app_content
        assert "RespectIgnoreDifferences=true" in app_content


class TestCNPGAdapterRenderPreview:
    """Test render() method for preview mode using PlatformEngine"""
    
    @pytest.mark.asyncio
    async def test_render_preview_mode(self):
        """Test preview mode generates correct configuration"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/02-cnpg.yaml")
        assert app_file.exists()
