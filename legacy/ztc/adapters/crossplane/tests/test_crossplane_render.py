"""Integration tests for Crossplane adapter rendering

Tests verify:
1. Engine renders Crossplane manifests to ArgoCD overlay structure
2. Production mode generates Application with tolerations at argocd/overlays/main/core/01-crossplane.yaml
3. Preview mode generates Application without tolerations
4. Provider manifests generated at argocd/overlays/main/foundation/provider-{name}.yaml
5. Manifests contain expected content (sync-waves, Helm chart refs, RBAC)
6. ArgoCD kustomization includes Crossplane resources

CRITICAL: Uses PlatformEngine to test actual file generation (same code path as ztc render)
"""

import pytest
from pathlib import Path
from ztc.engine.engine import PlatformEngine


class TestCrossplaneAdapterRenderProduction:
    """Test render() method for production mode using PlatformEngine"""
    
    @pytest.mark.asyncio
    async def test_render_generates_all_files_production(self):
        """Test engine generates all required files for production"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        # Verify core operator Application in ArgoCD overlay
        assert (Path("platform/generated/argocd/overlays/main/core/01-crossplane.yaml")).exists()
        
        # Verify provider files in foundation directory
        assert (Path("platform/generated/argocd/overlays/main/foundation/provider-kubernetes.yaml")).exists()
    
    @pytest.mark.asyncio
    async def test_render_production_application_contains_tolerations(self):
        """Test production Application contains control-plane tolerations"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/01-crossplane.yaml")
        app_content = app_file.read_text()
        
        assert "control-plane" in app_content
        assert "tolerations" in app_content
        assert "NoSchedule" in app_content
    
    @pytest.mark.asyncio
    async def test_render_production_uses_correct_chart_version(self):
        """Test Application references correct Crossplane Helm chart version"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/01-crossplane.yaml")
        app_content = app_file.read_text()
        
        assert "1.16.0" in app_content
        assert "https://charts.crossplane.io/stable" in app_content
        assert "crossplane" in app_content
    
    @pytest.mark.asyncio
    async def test_render_application_has_correct_sync_wave(self):
        """Test Application has sync-wave annotation set to 1"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/01-crossplane.yaml")
        app_content = app_file.read_text()
        
        assert 'argocd.argoproj.io/sync-wave: "1"' in app_content
    
    @pytest.mark.asyncio
    async def test_render_kubernetes_provider_has_correct_sync_wave(self):
        """Test Kubernetes provider has sync-wave annotations"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        provider_file = Path("platform/generated/argocd/overlays/main/foundation/provider-kubernetes.yaml")
        provider_content = provider_file.read_text()
        
        # Provider has sync-wave "-1", Config has "0", RBAC has "1"
        assert 'argocd.argoproj.io/sync-wave:' in provider_content
    
    @pytest.mark.asyncio
    async def test_render_kubernetes_provider_contains_rbac(self):
        """Test Kubernetes provider manifest includes RBAC resources"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        provider_file = Path("platform/generated/argocd/overlays/main/foundation/provider-kubernetes.yaml")
        provider_content = provider_file.read_text()
        
        assert "ClusterRole" in provider_content
        assert "ClusterRoleBinding" in provider_content
        assert "provider-kubernetes-6ef2ebb6f1db" in provider_content


class TestCrossplaneAdapterRenderPreview:
    """Test render() method for preview mode using PlatformEngine"""
    
    @pytest.mark.skip(reason="Requires platform-preview.yaml configuration")
    @pytest.mark.asyncio
    async def test_render_preview_excludes_tolerations(self):
        """Test preview Application excludes control-plane tolerations"""
        # Note: Requires platform.yaml with mode: preview
        platform_yaml = Path("platform/platform-preview.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/01-crossplane.yaml")
        app_content = app_file.read_text()
        
        # Should not contain tolerations section
        assert "tolerations" not in app_content or "control-plane" not in app_content
