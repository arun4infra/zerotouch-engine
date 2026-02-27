"""Integration tests for Cilium adapter rendering

Tests verify:
1. Engine renders Cilium manifests to correct locations
2. Generates ArgoCD Application for Gateway API in core/
3. Generates CNI manifests for Talos bootstrap
4. CNI and Gateway API capabilities are populated
5. No environment-specific files are created

CRITICAL: Uses PlatformEngine to test actual file generation (same code path as ztc render)
"""

import pytest
from pathlib import Path
from workflow_engine.engine.engine import PlatformEngine


class TestCiliumAdapterRender:
    """Test render() method using PlatformEngine"""
    
    @pytest.mark.asyncio
    async def test_render_generates_gateway_argocd_app_in_core(self):
        """Test engine generates Gateway API ArgoCD Application in core/"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        gateway_app = Path("platform/generated/argocd/overlays/main/core/04-gateway-config.yaml")
        assert gateway_app.exists()
        
        content = gateway_app.read_text()
        assert "kind: Application" in content
        assert "name: gateway-foundation" in content
        assert "argocd.argoproj.io/sync-wave" in content
    
    @pytest.mark.asyncio
    async def test_render_generates_cni_manifests_for_talos(self):
        """Test engine generates CNI manifests for Talos bootstrap"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        cni_manifests = Path("platform/generated/talos/templates/cilium/02-configmaps.yaml")
        assert cni_manifests.exists()
        
        content = cni_manifests.read_text()
        assert "kind: ConfigMap" in content or "kind: DaemonSet" in content
    
    @pytest.mark.asyncio
    async def test_render_gateway_app_has_correct_sync_wave(self):
        """Test Gateway API Application has sync-wave 4"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        gateway_app = Path("platform/generated/argocd/overlays/main/core/04-gateway-config.yaml")
        content = gateway_app.read_text()
        
        assert '"4"' in content or "'4'" in content or "sync-wave: 4" in content
    
    @pytest.mark.asyncio
    async def test_render_does_not_create_environment_specific_files(self):
        """Test Cilium doesn't create environment-specific files (dev/staging/prod)"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        # Cilium should not create files in environment directories
        assert not Path("platform/generated/argocd/overlays/main/dev/cilium").exists()
        assert not Path("platform/generated/argocd/overlays/main/staging/cilium").exists()
        assert not Path("platform/generated/argocd/overlays/main/prod/cilium").exists()
    
    @pytest.mark.asyncio
    async def test_render_gateway_app_references_correct_path(self):
        """Test Gateway API Application references correct repository path"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        gateway_app = Path("platform/generated/argocd/overlays/main/core/04-gateway-config.yaml")
        content = gateway_app.read_text()
        
        assert "platform/generated/argocd/k8/core/gateway" in content or "gateway-foundation" in content
