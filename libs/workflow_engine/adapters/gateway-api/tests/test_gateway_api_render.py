"""Integration tests for Gateway API adapter rendering

Tests verify:
1. Engine renders Gateway API manifests to platform/generated/
2. Production mode generates correct file structure with mode-specific config
3. Manifests contain expected content (sync-waves, resource refs, annotations)
4. All template files render without errors
5. Manifests are valid YAML with required fields

CRITICAL: Uses PlatformEngine to test actual file generation (same code path as ztc render)
"""

import pytest
from pathlib import Path
from ztc.engine.engine import PlatformEngine


class TestGatewayAPIAdapterRenderProduction:
    """Test render() method for production mode using PlatformEngine"""
    
    @pytest.mark.asyncio
    async def test_render_generates_crds_application(self):
        """Test engine generates CRD application manifest"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        crds_file = Path("platform/generated/argocd/base/00-gateway-api-crds.yaml")
        assert crds_file.exists(), "CRD application manifest should exist"
        
        crds_content = crds_file.read_text()
        assert "gateway-api-crds" in crds_content
        assert 'argocd.argoproj.io/sync-wave: "-2"' in crds_content
        assert "v1.4.1" in crds_content
        assert "kubernetes-sigs/gateway-api" in crds_content
    
    @pytest.mark.asyncio
    async def test_render_generates_foundation_manifests(self):
        """Test engine generates foundation manifests"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        foundation_dir = Path("platform/generated/argocd/overlays/main/core/gateway/gateway-foundation")
        assert foundation_dir.exists(), "Foundation directory should exist"
        
        # Check all foundation files
        assert (foundation_dir / "cilium-gateway-config.yaml").exists()
        assert (foundation_dir / "cilium-gateway-rbac.yaml").exists()
        assert (foundation_dir / "kustomization.yaml").exists()
        
        # Verify config content
        config_content = (foundation_dir / "cilium-gateway-config.yaml").read_text()
        assert "CiliumGatewayClassConfig" in config_content
        assert "LoadBalancer" in config_content
    
    @pytest.mark.asyncio
    async def test_render_generates_class_manifests(self):
        """Test engine generates class manifests"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        class_dir = Path("platform/generated/argocd/overlays/main/core/gateway/gateway-class")
        assert class_dir.exists(), "Class directory should exist"
        
        # Check all class files
        assert (class_dir / "cilium-gatewayclass.yaml").exists()
        assert (class_dir / "kustomization.yaml").exists()
        
        # Verify gatewayclass content
        gatewayclass_content = (class_dir / "cilium-gatewayclass.yaml").read_text()
        assert "kind: GatewayClass" in gatewayclass_content
        assert "name: cilium" in gatewayclass_content
        assert "io.cilium/gateway-controller" in gatewayclass_content
    
    @pytest.mark.asyncio
    async def test_render_generates_config_manifests(self):
        """Test engine generates config manifests"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        config_dir = Path("platform/generated/argocd/overlays/main/core/gateway/gateway-config")
        assert config_dir.exists(), "Config directory should exist"
        
        # Check all config files
        assert (config_dir / "bootstrap-issuer.yaml").exists()
        assert (config_dir / "letsencrypt-issuer.yaml").exists()
        assert (config_dir / "gateway-certificate.yaml").exists()
        assert (config_dir / "public-gateway.yaml").exists()
        assert (config_dir / "kustomization.yaml").exists()
    
    @pytest.mark.asyncio
    async def test_render_letsencrypt_issuer_contains_email(self):
        """Test Let's Encrypt issuer contains email from config"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        issuer_file = Path("platform/generated/argocd/overlays/main/core/gateway/gateway-config/letsencrypt-issuer.yaml")
        issuer_content = issuer_file.read_text()
        
        assert "admin@nutgraf.in" in issuer_content
        assert "letsencrypt-staging" in issuer_content
        assert "letsencrypt-production" in issuer_content
    
    @pytest.mark.asyncio
    async def test_render_certificate_contains_domain(self):
        """Test certificate contains domain from config"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        cert_file = Path("platform/generated/argocd/overlays/main/core/gateway/gateway-config/gateway-certificate.yaml")
        cert_content = cert_file.read_text()
        
        assert "nutgraf.in" in cert_content
        assert "*.nutgraf.in" in cert_content
        assert "nutgraf-in-tls-cert" in cert_content
    
    @pytest.mark.asyncio
    async def test_render_gateway_contains_hetzner_location(self):
        """Test gateway contains Hetzner location from config"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        gateway_file = Path("platform/generated/argocd/overlays/main/core/gateway/gateway-config/public-gateway.yaml")
        gateway_content = gateway_file.read_text()
        
        assert "load-balancer.hetzner.cloud/location: fsn1" in gateway_content
        assert "public-gateway" in gateway_content
        assert "gatewayClassName: cilium" in gateway_content
    
    @pytest.mark.asyncio
    async def test_render_generates_parent_application(self):
        """Test engine generates parent application with correct sync waves"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        parent_app_file = Path("platform/generated/argocd/overlays/main/core/04-gateway-config.yaml")
        assert parent_app_file.exists(), "Parent application should exist"
        
        parent_content = parent_app_file.read_text()
        
        # Check all three child applications
        assert "gateway-foundation" in parent_content
        assert "gateway-class" in parent_content
        assert "gateway-config" in parent_content
        
        # Check sync waves
        assert 'argocd.argoproj.io/sync-wave: "4"' in parent_content
        assert 'argocd.argoproj.io/sync-wave: "5"' in parent_content
        assert 'argocd.argoproj.io/sync-wave: "6"' in parent_content
    
    @pytest.mark.asyncio
    async def test_render_generates_environment_overlays(self):
        """Test engine generates environment-specific overlays"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        # Check environment-specific application overrides
        for env in ["dev", "staging", "prod"]:
            env_app_file = Path(f"platform/generated/argocd/overlays/main/{env}/04-gateway-config.yaml")
            assert env_app_file.exists(), f"{env} gateway-config application should exist"
            
            env_app_content = env_app_file.read_text()
            assert "gateway-config" in env_app_content
            assert f"path: platform/generated/argocd/overlays/main/{env}/gateway-config" in env_app_content
        
        # Check environment-specific kustomizations
        for env in ["dev", "staging", "prod"]:
            env_kustomization_file = Path(f"platform/generated/argocd/overlays/main/{env}/gateway-config/kustomization.yaml")
            assert env_kustomization_file.exists(), f"{env} gateway-config kustomization should exist"
            
            env_kustomization_content = env_kustomization_file.read_text()
            assert "../../core/gateway/gateway-config" in env_kustomization_content
            
            # Dev and staging should use letsencrypt-staging
            if env in ["dev", "staging"]:
                assert "letsencrypt-staging" in env_kustomization_content
                assert "patches:" in env_kustomization_content
            # Prod should not have patches (uses production issuer from core)
            elif env == "prod":
                assert "letsencrypt-staging" not in env_kustomization_content
    
    @pytest.mark.asyncio
    async def test_render_all_manifests_are_valid_yaml(self):
        """Test all generated manifests are valid YAML"""
        import yaml
        
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        # Collect all YAML files
        generated_dir = Path("platform/generated/argocd")
        yaml_files = list(generated_dir.rglob("*.yaml"))
        
        # Filter to gateway-api related files
        gateway_files = [
            f for f in yaml_files 
            if "gateway" in str(f) or "00-gateway-api-crds" in str(f)
        ]
        
        assert len(gateway_files) > 0, "Should have generated gateway-related YAML files"
        
        for yaml_file in gateway_files:
            if yaml_file.name == ".gitkeep":
                continue
            
            content = yaml_file.read_text()
            try:
                # Parse YAML to validate syntax
                yaml.safe_load_all(content)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {yaml_file}: {e}")


class TestGatewayAPIAdapterRenderPreview:
    """Test render() method for preview mode using PlatformEngine"""
    
    @pytest.mark.asyncio
    async def test_render_preview_generates_minimal_crds(self):
        """Test preview mode generates only minimal HTTPRoute CRD"""
        import shutil
        
        # Update platform.yaml to preview mode
        platform_yaml = Path("platform/platform.yaml")
        original_content = platform_yaml.read_text()
        
        try:
            # Clean generated directory
            generated_dir = Path("platform/generated")
            if generated_dir.exists():
                shutil.rmtree(generated_dir)
            
            # Temporarily set mode to preview
            preview_content = original_content.replace('mode: production', 'mode: preview')
            platform_yaml.write_text(preview_content)
            
            engine = PlatformEngine(platform_yaml)
            await engine.render()
            
            # Check preview CRDs file exists
            preview_crds_file = Path("platform/generated/argocd/overlays/preview/gateway-api-crds.yaml")
            assert preview_crds_file.exists(), "Preview CRDs manifest should exist"
            
            preview_content = preview_crds_file.read_text()
            assert "gateway-system" in preview_content
            assert "httproutes.gateway.networking.k8s.io" in preview_content
            assert "HTTPRoute" in preview_content
            
            # Verify gateway-api production files are NOT generated
            crds_file = Path("platform/generated/argocd/base/00-gateway-api-crds.yaml")
            assert not crds_file.exists(), "Production CRD application should not exist in preview mode"
            
            # Check gateway-specific directories don't exist
            gateway_foundation_dir = Path("platform/generated/argocd/overlays/main/core/gateway")
            assert not gateway_foundation_dir.exists(), "Gateway foundation directory should not exist in preview mode"
            
            # Verify file persists for manual inspection
            print(f"\n✓ Preview CRDs file generated at: {preview_crds_file}")
            print(f"✓ File size: {preview_crds_file.stat().st_size} bytes")
        
        finally:
            # Restore original content and regenerate production files
            platform_yaml.write_text(original_content)
            
            # Clean and regenerate for next tests
            if generated_dir.exists():
                shutil.rmtree(generated_dir)
            engine = PlatformEngine(platform_yaml)
            await engine.render()
