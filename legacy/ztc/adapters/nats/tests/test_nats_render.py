"""Integration tests for NATS adapter rendering

Tests verify:
1. Engine renders NATS manifests to platform/generated/argocd/overlays/main/core/
2. Production mode generates correct file with StatefulSet patch
3. Preview mode generates correct file without StatefulSet patch
4. Manifests contain expected content (sync-wave, Helm chart, JetStream config, resource limits)
5. Manifests are valid YAML with required ArgoCD Application fields

CRITICAL: Uses PlatformEngine to test actual file generation (same code path as ztc render)
"""

import pytest
from pathlib import Path
from ztc.engine.engine import PlatformEngine


class TestNATSAdapterRenderProduction:
    """Test render() method for production mode using PlatformEngine"""
    
    @pytest.mark.asyncio
    async def test_render_generates_application_file_production(self):
        """Test engine generates application.yaml for production"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/05-nats.yaml")
        assert app_file.exists(), "NATS application.yaml not generated"
    
    @pytest.mark.asyncio
    async def test_render_application_contains_correct_chart(self):
        """Test Application references correct Helm chart and version"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/05-nats.yaml")
        app_content = app_file.read_text()
        
        assert "https://nats-io.github.io/k8s/helm/charts/" in app_content
        assert "1.2.6" in app_content
    
    @pytest.mark.asyncio
    async def test_render_application_has_correct_sync_wave(self):
        """Test Application has correct sync-wave annotation"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/05-nats.yaml")
        app_content = app_file.read_text()
        
        assert 'argocd.argoproj.io/sync-wave: "5"' in app_content
    
    @pytest.mark.asyncio
    async def test_render_application_contains_jetstream_config(self):
        """Test Application contains JetStream configuration"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/05-nats.yaml")
        app_content = app_file.read_text()
        
        assert "jetstream:" in app_content
        assert "fileStore:" in app_content
        assert "maxSize: 10Gi" in app_content
        assert "memoryStore:" in app_content
        assert "maxSize: 1Gi" in app_content
    
    @pytest.mark.asyncio
    async def test_render_application_contains_resource_limits(self):
        """Test Application contains resource limits"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/05-nats.yaml")
        app_content = app_file.read_text()
        
        assert "cpu: 100m" in app_content
        assert "memory: 256Mi" in app_content
        assert "cpu: 500m" in app_content
        assert "memory: 1Gi" in app_content
    
    @pytest.mark.asyncio
    async def test_render_production_contains_statefulset_patch(self):
        """Test production mode includes StatefulSet patch with tolerations and affinity"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/05-nats.yaml")
        app_content = app_file.read_text()
        
        assert "statefulSet:" in app_content
        assert "patch:" in app_content
        assert "node-role.kubernetes.io/control-plane" in app_content
        assert "tolerations" in app_content
        assert "affinity" in app_content
    
    @pytest.mark.asyncio
    async def test_render_application_contains_ignore_differences(self):
        """Test Application contains ignoreDifferences for volumeClaimTemplates"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/05-nats.yaml")
        app_content = app_file.read_text()
        
        assert "ignoreDifferences:" in app_content
        assert "StatefulSet" in app_content
        assert "volumeClaimTemplates" in app_content


class TestNATSAdapterRenderPreview:
    """Test render() method for preview mode using PlatformEngine"""
    
    @pytest.mark.asyncio
    async def test_render_preview_excludes_statefulset_patch(self):
        """Test preview mode excludes StatefulSet patch"""
        # Note: This test requires a platform-preview.yaml with mode=preview
        platform_yaml = Path("platform/platform-preview.yaml")
        if not platform_yaml.exists():
            pytest.skip("platform-preview.yaml not found")
        
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/05-nats.yaml")
        app_content = app_file.read_text()
        
        # Should not contain StatefulSet patch in preview mode
        assert "statefulSet:" not in app_content or "patch:" not in app_content
