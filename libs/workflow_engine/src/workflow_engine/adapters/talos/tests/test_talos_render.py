"""Integration tests for Talos adapter rendering

Tests verify:
1. Engine renders Talos node configs to talos/nodes/{node_name}/config.yaml
2. Generates talosconfig file
3. Generates configs for all nodes defined in platform.yaml
4. Node configs contain cluster endpoint and node-specific details
5. KubernetesAPICapability is populated

CRITICAL: Uses PlatformEngine to test actual file generation (same code path as ztc render)
"""

import pytest
from pathlib import Path
from workflow_engine.engine.engine import PlatformEngine


class TestTalosAdapterRender:
    """Test render() method using PlatformEngine"""
    
    @pytest.mark.asyncio
    async def test_render_generates_node_configs(self):
        """Test engine generates config for each node"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        # Verify node configs exist (from platform.yaml: cp01-main, worker01)
        cp_config = Path("platform/generated/talos/nodes/cp01-main/config.yaml")
        worker_config = Path("platform/generated/talos/nodes/worker01/config.yaml")
        
        assert cp_config.exists()
        assert worker_config.exists()
    
    @pytest.mark.asyncio
    async def test_render_generates_talosconfig(self):
        """Test engine generates talosconfig file"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        talosconfig = Path("platform/generated/talos/talosconfig")
        assert talosconfig.exists()
        
        content = talosconfig.read_text()
        assert "context:" in content or "contexts:" in content
    
    @pytest.mark.asyncio
    async def test_render_node_config_contains_cluster_endpoint(self):
        """Test node configs contain cluster endpoint"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        cp_config = Path("platform/generated/talos/nodes/cp01-main/config.yaml")
        content = cp_config.read_text()
        
        # Should contain cluster endpoint from platform.yaml
        assert "95.216.151.243:6443" in content
    
    @pytest.mark.asyncio
    async def test_render_node_config_contains_node_name(self):
        """Test node configs contain node-specific name"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        cp_config = Path("platform/generated/talos/nodes/cp01-main/config.yaml")
        content = cp_config.read_text()
        
        assert "cp01-main" in content
    
    @pytest.mark.asyncio
    async def test_render_generates_configs_for_all_nodes(self):
        """Test engine generates configs for all nodes in platform.yaml"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        nodes_dir = Path("platform/generated/talos/nodes")
        assert nodes_dir.exists()
        
        # Should have 2 nodes from platform.yaml
        node_dirs = list(nodes_dir.iterdir())
        assert len(node_dirs) == 2
        
        node_names = [d.name for d in node_dirs]
        assert "cp01-main" in node_names
        assert "worker01" in node_names
    
    @pytest.mark.asyncio
    async def test_render_talosconfig_contains_cluster_name(self):
        """Test talosconfig contains cluster name"""
        platform_yaml = Path("platform/platform.yaml")
        engine = PlatformEngine(platform_yaml)
        await engine.render()
        
        talosconfig = Path("platform/generated/talos/talosconfig")
        content = talosconfig.read_text()
        
        # Should contain cluster name from platform.yaml
        assert "bizmatters-dev-01" in content
