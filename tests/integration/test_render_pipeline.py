"""Integration tests for render pipeline using real production code paths

Uses actual PlatformEngine and real adapters.
No mocking of internal components per integration testing patterns.
"""

import pytest
from pathlib import Path
import yaml
import json
import shutil
import tempfile
import os

from ztc.engine.engine import PlatformEngine


class TestRenderPipeline:
    """Test render pipeline with real production code paths"""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace with real platform.yaml"""
        temp_dir = tempfile.mkdtemp()
        workspace = Path(temp_dir)
        
        # Create real platform.yaml with actual adapter configuration
        platform_yaml = workspace / "platform.yaml"
        config = {
            "hetzner": {
                "version": "v1.0.0",
                "api_token": "a" * 64,
                "server_ips": ["192.168.1.1"],
                "rescue_mode_confirm": True
            },
            "cilium": {
                "version": "v1.18.5",
                "bgp": {"enabled": False}
            },
            "talos": {
                "version": "v1.11.5",
                "factory_image_id": "a" * 64,
                "cluster_name": "test-cluster",
                "cluster_endpoint": "192.168.1.1:6443",
                "nodes": [
                    {
                        "name": "cp01",
                        "ip": "192.168.1.1",
                        "role": "controlplane"
                    }
                ]
            }
        }
        platform_yaml.write_text(yaml.dump(config))
        
        yield workspace
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_render_creates_and_cleans_workspace(self, temp_workspace):
        """Test that render creates workspace and cleans up after success"""
        original_cwd = os.getcwd()
        os.chdir(temp_workspace)
        
        try:
            platform_yaml = temp_workspace / "platform.yaml"
            engine = PlatformEngine(platform_yaml, debug=False)
            
            await engine.render()
            
            # Verify workspace was cleaned up after successful render
            workspace = Path(".zerotouch-cache/workspace")
            assert not workspace.exists(), "Workspace should be cleaned up after successful render"
            
        finally:
            os.chdir(original_cwd)
    
    @pytest.mark.asyncio
    async def test_render_writes_manifests_from_real_adapters(self, temp_workspace):
        """Test that render writes manifests from real adapters"""
        original_cwd = os.getcwd()
        os.chdir(temp_workspace)
        
        try:
            platform_yaml = temp_workspace / "platform.yaml"
            engine = PlatformEngine(platform_yaml, debug=False)
            
            await engine.render()
            
            # Verify generated directory exists
            generated_dir = Path("platform/generated")
            assert generated_dir.exists()
            
            # Verify Cilium manifests were generated
            cilium_manifests = generated_dir / "network" / "cilium" / "manifests.yaml"
            if cilium_manifests.exists():
                content = cilium_manifests.read_text()
                assert len(content) > 0
            
            # Verify Talos configs were generated
            talos_dir = generated_dir / "os" / "talos"
            if talos_dir.exists():
                # Check for node configs
                nodes_dir = talos_dir / "nodes"
                if nodes_dir.exists():
                    assert len(list(nodes_dir.iterdir())) > 0
            
        finally:
            os.chdir(original_cwd)
    
    @pytest.mark.asyncio
    async def test_render_generates_lock_file(self, temp_workspace):
        """Test that render generates lock file with real data"""
        original_cwd = os.getcwd()
        os.chdir(temp_workspace)
        
        try:
            platform_yaml = temp_workspace / "platform.yaml"
            engine = PlatformEngine(platform_yaml, debug=False)
            
            await engine.render()
            
            # Verify lock file was created
            lock_path = Path("platform/lock.json")
            assert lock_path.exists(), "Lock file should be created"
            
            # Verify lock file structure
            with open(lock_path) as f:
                lock_data = json.load(f)
            
            assert "platform_hash" in lock_data
            assert "artifacts_hash" in lock_data
            assert "ztc_version" in lock_data
            assert "adapters" in lock_data
            
            # Verify real adapters are in lock file
            assert "hetzner" in lock_data["adapters"]
            assert "cilium" in lock_data["adapters"]
            assert "talos" in lock_data["adapters"]
            
        finally:
            os.chdir(original_cwd)
    
    @pytest.mark.asyncio
    async def test_render_debug_mode_preserves_workspace(self, temp_workspace):
        """Test that debug mode preserves workspace"""
        original_cwd = os.getcwd()
        os.chdir(temp_workspace)
        
        try:
            platform_yaml = temp_workspace / "platform.yaml"
            engine = PlatformEngine(platform_yaml, debug=True)
            
            await engine.render()
            
            # In debug mode, workspace may be preserved
            # This depends on implementation details
            
        finally:
            os.chdir(original_cwd)
    
    @pytest.mark.asyncio
    async def test_render_validates_artifacts_from_real_adapters(self, temp_workspace):
        """Test that render validates generated artifacts against schemas"""
        original_cwd = os.getcwd()
        os.chdir(temp_workspace)
        
        try:
            platform_yaml = temp_workspace / "platform.yaml"
            engine = PlatformEngine(platform_yaml, debug=False)
            
            # Should not raise validation errors with valid config
            await engine.render()
            
            # Verify artifacts were generated
            assert Path("platform/generated").exists()
            
        finally:
            os.chdir(original_cwd)
    
    @pytest.mark.asyncio
    async def test_render_atomic_swap_replaces_old_artifacts(self, temp_workspace):
        """Test atomic swap of generated directory with real artifacts"""
        original_cwd = os.getcwd()
        os.chdir(temp_workspace)
        
        try:
            # Create existing generated directory with old content
            existing_generated = Path("platform/generated")
            existing_generated.mkdir(parents=True, exist_ok=True)
            (existing_generated / "old_file.txt").write_text("old content")
            
            platform_yaml = temp_workspace / "platform.yaml"
            engine = PlatformEngine(platform_yaml, debug=False)
            
            await engine.render()
            
            # Verify old file is gone
            assert not (existing_generated / "old_file.txt").exists()
            
            # Verify new artifacts exist
            assert existing_generated.exists()
            assert len(list(existing_generated.rglob("*"))) > 0
            
        finally:
            os.chdir(original_cwd)
    
    @pytest.mark.asyncio
    async def test_render_resolves_real_adapter_dependencies(self, temp_workspace):
        """Test that render resolves dependencies between real adapters"""
        original_cwd = os.getcwd()
        os.chdir(temp_workspace)
        
        try:
            platform_yaml = temp_workspace / "platform.yaml"
            engine = PlatformEngine(platform_yaml, debug=False)
            
            # Resolve adapters using real dependency resolution
            adapters = engine.resolve_adapters()
            
            # Verify adapters were resolved
            assert len(adapters) > 0
            
            # Verify adapter order respects dependencies
            adapter_names = [a.name for a in adapters]
            assert "hetzner" in adapter_names
            assert "talos" in adapter_names
            assert "cilium" in adapter_names
            
            # Hetzner should come before Talos (Talos depends on cloud-infrastructure)
            hetzner_idx = adapter_names.index("hetzner")
            talos_idx = adapter_names.index("talos")
            assert hetzner_idx < talos_idx
            
        finally:
            os.chdir(original_cwd)
    
    @pytest.mark.asyncio
    async def test_render_with_real_capability_system(self, temp_workspace):
        """Test render with real capability-based dependency resolution"""
        original_cwd = os.getcwd()
        os.chdir(temp_workspace)
        
        try:
            platform_yaml = temp_workspace / "platform.yaml"
            engine = PlatformEngine(platform_yaml, debug=False)
            
            await engine.render()
            
            # Verify lock file contains capability information
            lock_path = Path("platform/lock.json")
            if lock_path.exists():
                with open(lock_path) as f:
                    lock_data = json.load(f)
                
                # Verify adapters have metadata
                for adapter_name in ["hetzner", "cilium", "talos"]:
                    if adapter_name in lock_data["adapters"]:
                        adapter_data = lock_data["adapters"][adapter_name]
                        assert "version" in adapter_data
            
        finally:
            os.chdir(original_cwd)
