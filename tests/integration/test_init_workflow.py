"""Integration tests for init workflow using real production code paths

Uses actual InitWorkflow, AdapterRegistry, and real adapters.
No mocking of internal components per integration testing patterns.
"""

import pytest
from pathlib import Path
from rich.console import Console
import yaml
import tempfile
import shutil
import os

from ztc.workflows.init import InitWorkflow
from ztc.registry.adapter_registry import AdapterRegistry
from ztc.registry.groups import SelectionGroup


class TestInitWorkflow:
    """Test InitWorkflow with real production code paths"""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace"""
        temp_dir = tempfile.mkdtemp()
        workspace = Path(temp_dir)
        yield workspace
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def console(self):
        """Real Rich console"""
        return Console()
    
    @pytest.fixture
    def registry(self):
        """Real adapter registry with actual adapters"""
        return AdapterRegistry()
    
    @pytest.fixture
    def workflow(self, console, registry):
        """Create InitWorkflow with real components"""
        return InitWorkflow(console, registry)
    
    def test_init_workflow_creation(self, workflow):
        """Test InitWorkflow instantiation with real registry"""
        assert workflow.config == {}
        assert len(workflow.selection_groups) > 0
        # Verify selection groups built from real adapters
        group_names = [g.name for g in workflow.selection_groups]
        assert "cloud_provider" in group_names or "foundation" in group_names
    
    def test_handle_group_selection(self, workflow):
        """Test group selection with real selection groups"""
        # Use actual selection group from workflow
        if len(workflow.selection_groups) > 0:
            group = workflow.selection_groups[0]
            
            # Simulate selection of default option
            result = group.default
            
            # Verify it's a valid adapter name
            assert result in group.options
    
    def test_load_existing_config(self, workflow, temp_workspace):
        """Test loading existing platform.yaml with real workflow"""
        original_cwd = os.getcwd()
        os.chdir(temp_workspace)
        
        try:
            # Create existing platform.yaml with real adapter config
            existing_config = {
                "hetzner": {
                    "version": "v1.0.0",
                    "api_token": "a" * 64,
                    "server_ips": ["192.168.1.1"],
                    "rescue_mode_confirm": True
                }
            }
            with open("platform.yaml", "w") as f:
                yaml.dump(existing_config, f)
            
            loaded_config = workflow.load_existing_config()
            
            assert loaded_config["hetzner"]["version"] == "v1.0.0"
            assert loaded_config["hetzner"]["api_token"] == "a" * 64
        finally:
            os.chdir(original_cwd)
    
    def test_write_platform_yaml(self, workflow, temp_workspace):
        """Test platform.yaml generation with real workflow"""
        original_cwd = os.getcwd()
        os.chdir(temp_workspace)
        
        try:
            # Set real adapter configuration
            workflow.config = {
                "hetzner": {
                    "version": "v1.0.0",
                    "api_token": "a" * 64,
                    "server_ips": ["192.168.1.1"],
                    "rescue_mode_confirm": True
                },
                "cilium": {
                    "version": "v1.18.5",
                    "bgp": {"enabled": False}
                }
            }
            
            workflow.write_platform_yaml()
            
            assert Path("platform.yaml").exists()
            
            with open("platform.yaml", "r") as f:
                config = yaml.safe_load(f)
            
            assert config["hetzner"]["version"] == "v1.0.0"
            assert config["cilium"]["version"] == "v1.18.5"
        finally:
            os.chdir(original_cwd)
    
    def test_collect_adapter_inputs_with_real_adapter(self, workflow, registry):
        """Test collect_adapter_inputs with real Hetzner adapter"""
        # Get real Hetzner adapter
        hetzner_adapter = registry.get_adapter("hetzner")
        
        # Pre-populate with valid config
        workflow.config = {
            "hetzner": {
                "version": "v1.0.0",
                "api_token": "a" * 64,
                "server_ips": ["192.168.1.1"],
                "rescue_mode_confirm": True
            }
        }
        
        # Should not prompt if config is valid
        workflow.collect_adapter_inputs(hetzner_adapter)
        
        # Config should remain unchanged
        assert workflow.config["hetzner"]["version"] == "v1.0.0"
    
    def test_validate_downstream_adapters_with_real_adapters(self, workflow, registry):
        """Test downstream adapter validation with real adapters"""
        # Get real adapters
        hetzner_adapter = registry.get_adapter("hetzner")
        
        # Setup config
        workflow.config = {
            "hetzner": {
                "version": "v1.0.0",
                "api_token": "a" * 64,
                "server_ips": ["192.168.1.1"],
                "rescue_mode_confirm": True
            },
            "talos": {
                "version": "v1.11.5",
                "factory_image_id": "test-id",
                "cluster_name": "test",
                "cluster_endpoint": "192.168.1.1:6443",
                "nodes": []
            }
        }
        
        # Validate downstream adapters
        workflow.validate_downstream_adapters(hetzner_adapter)
        
        # Should not raise errors with valid config
        assert "talos" in workflow.config
    
    def test_display_summary_with_real_config(self, workflow):
        """Test summary display with real adapter configuration"""
        workflow.config = {
            "hetzner": {
                "version": "v1.0.0",
                "api_token": "a" * 64,
                "server_ips": ["192.168.1.1"],
                "rescue_mode_confirm": True
            },
            "cilium": {
                "version": "v1.18.5",
                "bgp": {"enabled": False}
            }
        }
        
        # Should not raise exception
        workflow.display_summary()
    
    def test_selection_groups_built_from_real_adapters(self, workflow, registry):
        """Test that selection groups are built from real adapter metadata"""
        # Verify selection groups exist
        assert len(workflow.selection_groups) > 0
        
        # Verify each group has valid options from real adapters
        for group in workflow.selection_groups:
            assert len(group.options) > 0
            assert group.default in group.options
            
            # Verify each option is a real adapter
            for option in group.options:
                adapter = registry.get_adapter(option)
                assert adapter is not None
                assert adapter.name == option
    
    def test_get_required_inputs_from_real_adapters(self, registry):
        """Test that real adapters return valid input prompts"""
        # Test Hetzner adapter
        hetzner = registry.get_adapter("hetzner")
        inputs = hetzner.get_required_inputs()
        
        assert len(inputs) > 0
        assert any(inp.name == "api_token" for inp in inputs)
        assert any(inp.name == "server_ips" for inp in inputs)
        
        # Test Cilium adapter
        cilium = registry.get_adapter("cilium")
        inputs = cilium.get_required_inputs()
        
        assert len(inputs) > 0
        assert any(inp.name == "version" for inp in inputs)
        
        # Test Talos adapter
        talos = registry.get_adapter("talos")
        inputs = talos.get_required_inputs()
        
        assert len(inputs) > 0
        assert any(inp.name == "cluster_name" for inp in inputs)
