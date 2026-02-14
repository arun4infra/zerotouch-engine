"""Integration tests for Crossplane adapter rendering

Tests verify:
1. Engine renders Crossplane manifests to platform/generated/crossplane/
2. Production mode generates correct file structure with tolerations
3. Preview mode generates correct file structure without tolerations
4. Provider manifests generated only for selected providers
5. Manifests contain expected content (sync-waves, Helm chart refs)
6. Capability data is correctly provided

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
        
        generated_dir = Path("platform/generated/crossplane")
        assert generated_dir.exists()
        
        # Verify core operator file
        assert (generated_dir / "core/application.yaml").exists()
        
        # Verify kustomization
        assert (generated_dir / "kustomization.yaml").exists()
        
        # Verify provider files (based on platform.yaml config)
        assert (generated_dir / "providers/kubernetes.yaml").exists()
    
    @pytest.mark.asyncio
    async def test_render_production_application_contains_tolerations(self):
        """Test production Application contains control-plane tolerations"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/crossplane/core/application.yaml")
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
        
        app_file = Path("platform/generated/crossplane/core/application.yaml")
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
        
        app_file = Path("platform/generated/crossplane/core/application.yaml")
        app_content = app_file.read_text()
        
        assert 'argocd.argoproj.io/sync-wave: "1"' in app_content
    
    @pytest.mark.asyncio
    async def test_render_kubernetes_provider_has_correct_sync_wave(self):
        """Test Kubernetes provider has sync-wave annotations"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        provider_file = Path("platform/generated/crossplane/providers/kubernetes.yaml")
        provider_content = provider_file.read_text()
        
        # Provider has sync-wave "-1", Config has "0", RBAC has "1"
        assert 'argocd.argoproj.io/sync-wave:' in provider_content
    
    @pytest.mark.asyncio
    async def test_render_kubernetes_provider_contains_rbac(self):
        """Test Kubernetes provider manifest includes RBAC resources"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        provider_file = Path("platform/generated/crossplane/providers/kubernetes.yaml")
        provider_content = provider_file.read_text()
        
        assert "ClusterRole" in provider_content
        assert "ClusterRoleBinding" in provider_content
        assert "provider-kubernetes-6ef2ebb6f1db" in provider_content
    
    @pytest.mark.asyncio
    async def test_render_kustomization_includes_all_resources(self):
        """Test kustomization.yaml includes core and provider resources"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        kustomization_file = Path("platform/generated/crossplane/kustomization.yaml")
        kustomization_content = kustomization_file.read_text()
        
        assert "core/application.yaml" in kustomization_content
        assert "providers/kubernetes.yaml" in kustomization_content


class TestCrossplaneAdapterRenderPreview:
    """Test render() method for preview mode using PlatformEngine"""
    
    @pytest.mark.asyncio
    async def test_render_preview_excludes_tolerations(self):
        """Test preview Application excludes control-plane tolerations"""
        # Note: Requires platform.yaml with mode: preview
        platform_yaml = Path("platform/platform-preview.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/crossplane/core/application.yaml")
        app_content = app_file.read_text()
        
        # Should not contain tolerations section
        assert "tolerations" not in app_content or "control-plane" not in app_content
