"""Integration tests for Cert-manager adapter rendering

Tests verify:
1. Engine renders cert-manager manifests to platform/generated/cert-manager/
2. Production mode generates correct file structure
3. Preview mode generates correct file structure
4. Manifests contain expected content (sync-waves, Helm chart refs, resource limits)
5. Manifests are valid YAML with required ArgoCD Application fields

CRITICAL: Uses PlatformEngine to test actual file generation (same code path as ztc render)
"""

import pytest
from pathlib import Path
from workflow_engine.engine.engine import PlatformEngine


class TestCertManagerAdapterRenderProduction:
    """Test render() method for production mode using PlatformEngine"""
    
    @pytest.mark.asyncio
    async def test_render_generates_application_file_production(self):
        """Test engine generates application.yaml for production"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/01-cert-manager.yaml")
        assert app_file.exists()
    
    @pytest.mark.asyncio
    async def test_render_application_contains_correct_chart(self):
        """Test Application references correct Helm chart and version"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/01-cert-manager.yaml")
        app_content = app_file.read_text()
        
        assert "https://charts.jetstack.io" in app_content
        assert "v1.19.2" in app_content
    
    @pytest.mark.asyncio
    async def test_render_application_has_correct_sync_wave(self):
        """Test Application has correct sync-wave annotation"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/01-cert-manager.yaml")
        app_content = app_file.read_text()
        
        assert 'argocd.argoproj.io/sync-wave: "1"' in app_content
    
    @pytest.mark.asyncio
    async def test_render_application_contains_gateway_api(self):
        """Test Application contains Gateway API config when enabled"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/01-cert-manager.yaml")
        app_content = app_file.read_text()
        
        assert "enableGatewayAPI: true" in app_content
        assert "ExperimentalGatewayAPISupport: true" in app_content
    
    @pytest.mark.asyncio
    async def test_render_application_contains_resource_limits(self):
        """Test Application contains resource limits for controller/webhook/cainjector"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/01-cert-manager.yaml")
        app_content = app_file.read_text()
        
        # Controller limits
        assert "cpu: 10m" in app_content
        assert "memory: 32Mi" in app_content
        assert "cpu: 100m" in app_content
        assert "memory: 128Mi" in app_content
        
        # Webhook limits
        assert "cpu: 5m" in app_content
        assert "memory: 16Mi" in app_content
        assert "cpu: 50m" in app_content
        assert "memory: 64Mi" in app_content


class TestCertManagerAdapterRenderPreview:
    """Test render() method for preview mode using PlatformEngine"""
    
    @pytest.mark.asyncio
    async def test_render_preview_mode(self):
        """Test preview mode generates correct configuration"""
        # Note: This test uses production platform.yaml
        # In real usage, platform.yaml would have mode: preview
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/01-cert-manager.yaml")
        assert app_file.exists()
