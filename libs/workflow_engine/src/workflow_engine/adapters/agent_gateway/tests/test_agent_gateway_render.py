"""Integration tests for Agent Gateway adapter rendering

Tests verify:
1. Engine renders Agent Gateway manifests to platform/generated/
2. Application manifest contains correct sync-wave
3. Manifests directory contains configmap, deployment, service, kustomization
4. HTTPRoute directory contains httproute and kustomization
5. ConfigMap contains extAuthz configuration
6. HTTPRoute references public-gateway
7. All manifests are valid YAML

CRITICAL: Uses PlatformEngine to test actual file generation (same code path as ztc render)
"""

import pytest
from pathlib import Path
from workflow_engine.engine.engine import PlatformEngine


class TestAgentGatewayAdapterRender:
    """Test render() method using PlatformEngine"""
    
    @pytest.mark.asyncio
    async def test_render_generates_application_manifest(self):
        """Test engine generates application manifest"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/base/06-agentgateway.yaml")
        assert app_file.exists(), "Application manifest should exist"
        
        app_content = app_file.read_text()
        assert "agentgateway" in app_content
        assert 'argocd.argoproj.io/sync-wave: "6"' in app_content
        assert "platform-agent-gateway" in app_content
    
    @pytest.mark.asyncio
    async def test_render_generates_manifest_files(self):
        """Test engine generates all manifest files"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        manifests_dir = Path("platform/generated/argocd/overlays/main/core/agentgateway")
        assert manifests_dir.exists(), "Manifests directory should exist"
        
        assert (manifests_dir / "configmap.yaml").exists()
        assert (manifests_dir / "deployment.yaml").exists()
        assert (manifests_dir / "service.yaml").exists()
        assert (manifests_dir / "kustomization.yaml").exists()
    
    @pytest.mark.asyncio
    async def test_render_generates_httproute_files(self):
        """Test engine generates HTTPRoute files"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        httproute_dir = Path("platform/generated/argocd/overlays/main/core/agentgateway-httproute")
        assert httproute_dir.exists(), "HTTPRoute directory should exist"
        
        assert (httproute_dir / "httproute.yaml").exists()
        assert (httproute_dir / "kustomization.yaml").exists()
    
    @pytest.mark.asyncio
    async def test_configmap_contains_extauthz_config(self):
        """Test configmap contains extAuthz configuration"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        configmap_file = Path("platform/generated/argocd/overlays/main/core/agentgateway/configmap.yaml")
        configmap_content = configmap_file.read_text()
        
        # Check routing rules
        assert "name: auth" in configmap_content
        assert "name: api" in configmap_content
        assert "pathPrefix: \"/auth\"" in configmap_content
        assert "pathPrefix: \"/api\"" in configmap_content
        
        # Check extAuthz configuration
        assert "extAuthz:" in configmap_content
        assert "identity-service.platform-identity.svc.cluster.local:3000" in configmap_content
        assert "includeRequestHeaders:" in configmap_content
        assert "includeResponseHeaders:" in configmap_content
        assert "requestHeaderModifier:" in configmap_content
    
    @pytest.mark.asyncio
    async def test_httproute_references_public_gateway(self):
        """Test HTTPRoute references public-gateway"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        httproute_file = Path("platform/generated/argocd/overlays/main/core/agentgateway-httproute/httproute.yaml")
        httproute_content = httproute_file.read_text()
        
        assert "kind: HTTPRoute" in httproute_content
        assert "name: public-gateway" in httproute_content
        assert "namespace: kube-system" in httproute_content
        assert "agentgateway.nutgraf.in" in httproute_content
    
    @pytest.mark.asyncio
    async def test_deployment_uses_configured_image_tag(self):
        """Test deployment uses configured image tag"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        deployment_file = Path("platform/generated/argocd/overlays/main/core/agentgateway/deployment.yaml")
        deployment_content = deployment_file.read_text()
        
        assert "ghcr.io/agentgateway/agentgateway:latest" in deployment_content
    
    @pytest.mark.asyncio
    async def test_all_manifests_are_valid_yaml(self):
        """Test all generated manifests are valid YAML"""
        import yaml
        
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        # Check application manifest
        app_file = Path("platform/generated/argocd/base/06-agentgateway.yaml")
        try:
            yaml.safe_load(app_file.read_text())
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML in application manifest: {e}")
        
        # Check manifest files
        manifests_dir = Path("platform/generated/argocd/overlays/main/core/agentgateway")
        for yaml_file in manifests_dir.glob("*.yaml"):
            try:
                yaml.safe_load(yaml_file.read_text())
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {yaml_file}: {e}")
        
        # Check HTTPRoute files
        httproute_dir = Path("platform/generated/argocd/overlays/main/core/agentgateway-httproute")
        for yaml_file in httproute_dir.glob("*.yaml"):
            try:
                yaml.safe_load(yaml_file.read_text())
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {yaml_file}: {e}")
