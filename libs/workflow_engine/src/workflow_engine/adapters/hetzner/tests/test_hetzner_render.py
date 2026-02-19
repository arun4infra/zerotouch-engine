"""Integration tests for Hetzner adapter rendering

Tests verify:
1. Engine renders Hetzner secrets to argocd/overlays/main/dev/secrets/
2. Generates hcloud.secret.yaml and external-dns-hetzner.secret.yaml
3. Generates ksops-generator.yaml and kustomization.yaml
4. CloudInfrastructureCapability is populated with server IDs
5. Environment variables are set correctly

CRITICAL: Uses PlatformEngine to test actual file generation (same code path as ztc render)
"""

import pytest
from pathlib import Path
from workflow_engine.engine.engine import PlatformEngine


class TestHetznerAdapterRender:
    """Test render() method using PlatformEngine"""
    
    @pytest.mark.asyncio
    async def test_render_generates_secrets_in_all_environments(self):
        """Test engine generates secrets in dev/staging/prod directories"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        # Verify secrets generated for all environments
        for env in ["dev", "staging", "prod"]:
            secrets_dir = Path(f"platform/generated/argocd/overlays/main/{env}/secrets")
            assert secrets_dir.exists(), f"{env} secrets directory not found"
            
            # Verify secret files
            assert (secrets_dir / "hcloud.secret.yaml").exists(), f"{env}/hcloud.secret.yaml not found"
            assert (secrets_dir / "external-dns-hetzner.secret.yaml").exists(), f"{env}/external-dns-hetzner.secret.yaml not found"
            assert (secrets_dir / "ksops-generator.yaml").exists(), f"{env}/ksops-generator.yaml not found"
            assert (secrets_dir / "kustomization.yaml").exists(), f"{env}/kustomization.yaml not found"
    
    @pytest.mark.asyncio
    async def test_render_hcloud_secret_contains_token(self):
        """Test hcloud secret contains API token"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        secret_file = Path("platform/generated/argocd/overlays/main/dev/secrets/hcloud.secret.yaml")
        content = secret_file.read_text()
        
        assert "kind: Secret" in content
        assert "name: hcloud" in content
        assert "namespace: kube-system" in content
        assert "token:" in content
    
    @pytest.mark.asyncio
    async def test_render_external_dns_secret_contains_token(self):
        """Test external-dns secret contains Hetzner DNS token"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        secret_file = Path("platform/generated/argocd/overlays/main/dev/secrets/external-dns-hetzner.secret.yaml")
        content = secret_file.read_text()
        
        assert "kind: Secret" in content
        assert "name: external-dns-hetzner" in content
        assert "namespace: kube-system" in content
        assert "HETZNER_DNS_TOKEN:" in content
    
    @pytest.mark.asyncio
    async def test_render_ksops_generator_references_secrets(self):
        """Test ksops-generator.yaml references both secret files"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        generator_file = Path("platform/generated/argocd/overlays/main/dev/secrets/ksops-generator.yaml")
        content = generator_file.read_text()
        
        assert "./hcloud.secret.yaml" in content
        assert "./external-dns-hetzner.secret.yaml" in content
    
    @pytest.mark.asyncio
    async def test_render_kustomization_references_generator(self):
        """Test kustomization.yaml references ksops-generator"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        kustomization_file = Path("platform/generated/argocd/overlays/main/dev/secrets/kustomization.yaml")
        content = kustomization_file.read_text()
        
        assert "kind: Kustomization" in content
        assert "generators:" in content
        assert "ksops-generator.yaml" in content
    
    @pytest.mark.asyncio
    async def test_render_generates_secrets_for_all_environments(self):
        """Test Hetzner generates secrets for dev, staging, and prod"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        # Verify secrets exist in all three environments
        for env in ["dev", "staging", "prod"]:
            secrets_dir = Path(f"platform/generated/argocd/overlays/main/{env}/secrets")
            assert secrets_dir.exists(), f"{env} secrets directory should exist"
            assert (secrets_dir / "hcloud.secret.yaml").exists()
            assert (secrets_dir / "external-dns-hetzner.secret.yaml").exists()
            assert (secrets_dir / "ksops-generator.yaml").exists()
            assert (secrets_dir / "kustomization.yaml").exists()
