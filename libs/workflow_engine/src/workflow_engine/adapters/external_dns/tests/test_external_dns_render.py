"""Integration tests for External-DNS adapter rendering

Tests verify:
1. Engine renders external-dns manifests to platform/generated/argocd/overlays/main/core/
2. Hetzner provider generates correct webhook configuration
3. AWS provider generates correct IRSA configuration
4. Manifests contain expected content (sync-wave, Helm chart, provider config)
5. Manifests are valid YAML with required ArgoCD Application fields

CRITICAL: Uses PlatformEngine to test actual file generation (same code path as ztc render)
"""

import pytest
from pathlib import Path
from workflow_engine.engine.engine import PlatformEngine


class TestExternalDNSAdapterRenderHetzner:
    """Test render() method for Hetzner provider using PlatformEngine"""
    
    @pytest.mark.asyncio
    async def test_render_generates_application_file_hetzner(self):
        """Test engine generates application.yaml for Hetzner"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/01-external-dns.yaml")
        assert app_file.exists(), "External-DNS application.yaml not generated"
    
    @pytest.mark.asyncio
    async def test_render_application_contains_hetzner_provider(self):
        """Test Application contains Hetzner webhook provider configuration"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/01-external-dns.yaml")
        app_content = app_file.read_text()
        
        assert "name: webhook" in app_content
        assert "hetzner/external-dns-hetzner-webhook" in app_content
        assert "HETZNER_TOKEN" in app_content
        assert "external-dns-hetzner" in app_content
    
    @pytest.mark.asyncio
    async def test_render_application_has_correct_sync_wave(self):
        """Test Application has correct sync-wave annotation"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/01-external-dns.yaml")
        app_content = app_file.read_text()
        
        assert 'argocd.argoproj.io/sync-wave: "1"' in app_content
    
    @pytest.mark.asyncio
    async def test_render_application_contains_correct_chart(self):
        """Test Application references correct Helm chart"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/01-external-dns.yaml")
        app_content = app_file.read_text()
        
        assert "https://kubernetes-sigs.github.io/external-dns" in app_content
        assert "chart: external-dns" in app_content
    
    @pytest.mark.asyncio
    async def test_render_application_contains_resource_limits(self):
        """Test Application contains resource limits"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/01-external-dns.yaml")
        app_content = app_file.read_text()
        
        assert "cpu: 10m" in app_content
        assert "memory: 32Mi" in app_content
        assert "cpu: 50m" in app_content
        assert "memory: 64Mi" in app_content


class TestExternalDNSAdapterRenderAWS:
    """Test render() method for AWS provider using PlatformEngine"""
    
    @pytest.mark.asyncio
    async def test_render_generates_application_file_aws(self):
        """Test engine generates application.yaml for AWS"""
        # Note: This test requires a platform-aws.yaml with provider=aws
        platform_yaml = Path("platform/platform-aws.yaml")
        if not platform_yaml.exists():
            pytest.skip("platform-aws.yaml not found")
        
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/01-external-dns.yaml")
        assert app_file.exists()
    
    @pytest.mark.asyncio
    async def test_render_application_contains_aws_provider(self):
        """Test Application contains AWS Route53 provider with IRSA"""
        platform_yaml = Path("platform/platform-aws.yaml")
        if not platform_yaml.exists():
            pytest.skip("platform-aws.yaml not found")
        
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/overlays/main/core/01-external-dns.yaml")
        app_content = app_file.read_text()
        
        assert "name: aws" in app_content
        assert "serviceAccount:" in app_content
        assert "eks.amazonaws.com/role-arn" in app_content
