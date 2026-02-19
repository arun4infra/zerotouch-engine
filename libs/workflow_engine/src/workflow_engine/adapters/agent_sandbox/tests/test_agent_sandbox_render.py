"""Integration tests for Agent Sandbox adapter rendering

Tests verify:
1. Engine renders Agent Sandbox manifests to platform/generated/
2. Application manifest contains correct sync-wave and namespace
3. Wrapper kustomization contains 8 raw GitHub resources
4. Image patch correctly replaces ko:// with configured registry
5. Args patch includes --extensions flag
6. All manifests are valid YAML

CRITICAL: Uses PlatformEngine to test actual file generation (same code path as ztc render)
"""

import pytest
from pathlib import Path
from workflow_engine.engine.engine import PlatformEngine


class TestAgentSandboxAdapterRender:
    """Test render() method using PlatformEngine"""
    
    @pytest.mark.asyncio
    async def test_render_generates_application_manifest(self):
        """Test engine generates application manifest"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/base/04-agent-sandbox.yaml")
        assert app_file.exists(), "Application manifest should exist"
        
        app_content = app_file.read_text()
        assert "agent-sandbox-controller" in app_content
        assert 'argocd.argoproj.io/sync-wave: "4"' in app_content
        assert "agent-sandbox-system" in app_content
    
    @pytest.mark.asyncio
    async def test_render_generates_wrapper_kustomization(self):
        """Test engine generates wrapper kustomization"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        wrapper_file = Path("platform/generated/argocd/base/agent-sandbox-wrapper/kustomization.yaml")
        assert wrapper_file.exists(), "Wrapper kustomization should exist"
        
        wrapper_content = wrapper_file.read_text()
        assert "kind: Kustomization" in wrapper_content
    
    @pytest.mark.asyncio
    async def test_wrapper_contains_eight_resources(self):
        """Test wrapper kustomization contains 8 raw GitHub resources"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        wrapper_file = Path("platform/generated/argocd/base/agent-sandbox-wrapper/kustomization.yaml")
        wrapper_content = wrapper_file.read_text()
        
        # Check all 8 resources
        assert "controller.yaml" in wrapper_content
        assert "rbac.generated.yaml" in wrapper_content
        assert "extensions.yaml" in wrapper_content
        assert "extensions-rbac.generated.yaml" in wrapper_content
        assert "agents.x-k8s.io_sandboxes.yaml" in wrapper_content
        assert "extensions.agents.x-k8s.io_sandboxclaims.yaml" in wrapper_content
        assert "extensions.agents.x-k8s.io_sandboxtemplates.yaml" in wrapper_content
        assert "extensions.agents.x-k8s.io_sandboxwarmpools.yaml" in wrapper_content
        
        # Count raw GitHub URLs
        github_urls = wrapper_content.count("https://raw.githubusercontent.com/kubernetes-sigs/agent-sandbox/main/k8s/")
        assert github_urls == 8, f"Should have 8 GitHub URLs, found {github_urls}"
    
    @pytest.mark.asyncio
    async def test_image_patch_replaces_ko_prefix(self):
        """Test image patch correctly replaces ko:// with configured registry"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        wrapper_file = Path("platform/generated/argocd/base/agent-sandbox-wrapper/kustomization.yaml")
        wrapper_content = wrapper_file.read_text()
        
        # Check image patch structure
        assert "images:" in wrapper_content
        assert "name: ko://sigs.k8s.io/agent-sandbox/cmd/agent-sandbox-controller" in wrapper_content
        assert "newName: us-central1-docker.pkg.dev/k8s-staging-images/agent-sandbox/agent-sandbox-controller" in wrapper_content
        assert "newTag: latest-main" in wrapper_content
    
    @pytest.mark.asyncio
    async def test_args_patch_includes_extensions_flag(self):
        """Test args patch includes --extensions flag"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        wrapper_file = Path("platform/generated/argocd/base/agent-sandbox-wrapper/kustomization.yaml")
        wrapper_content = wrapper_file.read_text()
        
        # Check args patch structure
        assert "patches:" in wrapper_content
        assert "kind: StatefulSet" in wrapper_content
        assert "name: agent-sandbox-controller" in wrapper_content
        assert "namespace: agent-sandbox-system" in wrapper_content
        assert '"--extensions"' in wrapper_content
        assert "op: add" in wrapper_content
        assert "path: /spec/template/spec/containers/0/args" in wrapper_content
    
    @pytest.mark.asyncio
    async def test_application_references_wrapper_path(self):
        """Test application manifest references correct wrapper path"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        app_file = Path("platform/generated/argocd/base/04-agent-sandbox.yaml")
        app_content = app_file.read_text()
        
        assert "path: platform/generated/argocd/base/agent-sandbox-wrapper" in app_content
    
    @pytest.mark.asyncio
    async def test_all_manifests_are_valid_yaml(self):
        """Test all generated manifests are valid YAML"""
        import yaml
        
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        # Check application manifest
        app_file = Path("platform/generated/argocd/base/04-agent-sandbox.yaml")
        app_content = app_file.read_text()
        try:
            yaml.safe_load(app_content)
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML in application manifest: {e}")
        
        # Check wrapper kustomization
        wrapper_file = Path("platform/generated/argocd/base/agent-sandbox-wrapper/kustomization.yaml")
        wrapper_content = wrapper_file.read_text()
        try:
            yaml.safe_load(wrapper_content)
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML in wrapper kustomization: {e}")
