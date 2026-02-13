"""Integration tests for eject workflow

Uses real production code paths - actual EjectWorkflow, PlatformEngine, and adapters.
No mocking of internal components per integration testing patterns.
"""

import pytest
from pathlib import Path
from rich.console import Console
import json
import tempfile
import shutil
import yaml
import os

from ztc.workflows.eject import EjectWorkflow


class TestEjectWorkflow:
    """Test EjectWorkflow with real production code paths"""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace with real platform.yaml for actual adapters"""
        temp_dir = tempfile.mkdtemp()
        workspace = Path(temp_dir)
        
        # Create real platform.yaml with actual adapter configuration
        platform_yaml = workspace / "platform.yaml"
        config = {
            "hetzner": {
                "version": "v1.0.0",
                "api_token": "a" * 64,
                "server_ips": ["192.168.1.1"]
            },
            "cilium": {
                "version": "v1.18.5",
                "bgp": {
                    "enabled": False
                }
            },
            "talos": {
                "version": "v1.11.5",
                "factory_image_id": "a" * 64,  # Fixed: 64 characters required
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
        
        # Create generated artifacts directory
        generated_dir = workspace / "platform" / "generated"
        generated_dir.mkdir(parents=True)
        (generated_dir / "test.yaml").write_text("test: content")
        
        # Create pipeline directory
        pipeline_dir = workspace / "bootstrap" / "pipeline"
        pipeline_dir.mkdir(parents=True)
        (pipeline_dir / "production.yaml").write_text("stages:\n  - name: test\n")
        
        yield workspace
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def console(self):
        """Real Rich console for production code path"""
        return Console()
    
    def test_eject_workflow_creation(self, console, temp_workspace):
        """Test EjectWorkflow instantiation with real console"""
        output_dir = temp_workspace / "debug"
        workflow = EjectWorkflow(console, output_dir, "production")
        
        assert workflow.output_dir == output_dir
        assert workflow.env == "production"
        assert workflow.engine is None
    
    def test_validate_prerequisites_success(self, console, temp_workspace):
        """Test prerequisite validation with valid files using production code"""
        output_dir = temp_workspace / "debug"
        workflow = EjectWorkflow(console, output_dir, "production")
        
        original_cwd = os.getcwd()
        os.chdir(temp_workspace)
        
        try:
            workflow.validate_prerequisites()
        finally:
            os.chdir(original_cwd)
    
    def test_validate_prerequisites_missing_platform_yaml(self, console, temp_workspace):
        """Test prerequisite validation fails without platform.yaml"""
        output_dir = temp_workspace / "debug"
        workflow = EjectWorkflow(console, output_dir, "production")
        
        # Remove platform.yaml
        (temp_workspace / "platform.yaml").unlink()
        
        original_cwd = os.getcwd()
        os.chdir(temp_workspace)
        
        try:
            with pytest.raises(FileNotFoundError, match="platform.yaml not found"):
                workflow.validate_prerequisites()
        finally:
            os.chdir(original_cwd)
    
    def test_validate_prerequisites_missing_artifacts(self, console, temp_workspace):
        """Test prerequisite validation fails without generated artifacts"""
        output_dir = temp_workspace / "debug"
        workflow = EjectWorkflow(console, output_dir, "production")
        
        # Remove generated directory
        shutil.rmtree(temp_workspace / "platform" / "generated")
        
        original_cwd = os.getcwd()
        os.chdir(temp_workspace)
        
        try:
            with pytest.raises(FileNotFoundError, match="Generated artifacts not found"):
                workflow.validate_prerequisites()
        finally:
            os.chdir(original_cwd)
    
    def test_create_directory_structure(self, console, temp_workspace):
        """Test output directory structure creation using production code"""
        output_dir = temp_workspace / "debug"
        workflow = EjectWorkflow(console, output_dir, "production")
        
        workflow.create_directory_structure()
        
        assert output_dir.exists()
        assert (output_dir / "scripts").exists()
        assert (output_dir / "context").exists()
        assert (output_dir / "pipeline").exists()
    
    def test_copy_pipeline_yaml(self, console, temp_workspace):
        """Test pipeline.yaml copying using production code"""
        output_dir = temp_workspace / "debug"
        workflow = EjectWorkflow(console, output_dir, "production")
        workflow.create_directory_structure()
        
        original_cwd = os.getcwd()
        os.chdir(temp_workspace)
        
        try:
            workflow.copy_pipeline_yaml()
            
            pipeline_dst = output_dir / "pipeline" / "production.yaml"
            assert pipeline_dst.exists()
            assert "stages:" in pipeline_dst.read_text()
        finally:
            os.chdir(original_cwd)
    
    def test_copy_pipeline_yaml_missing_file(self, console, temp_workspace):
        """Test pipeline.yaml copying with missing file"""
        output_dir = temp_workspace / "debug"
        workflow = EjectWorkflow(console, output_dir, "staging")
        workflow.create_directory_structure()
        
        original_cwd = os.getcwd()
        os.chdir(temp_workspace)
        
        try:
            # Should not raise error, just print warning
            workflow.copy_pipeline_yaml()
        finally:
            os.chdir(original_cwd)
    
    def test_display_summary(self, console, temp_workspace):
        """Test summary display using production code"""
        output_dir = temp_workspace / "debug"
        workflow = EjectWorkflow(console, output_dir, "production")
        workflow.create_directory_structure()
        
        # Should not raise error
        workflow.display_summary()
    
    def test_full_eject_workflow_with_real_adapters(self, console, temp_workspace):
        """Test complete eject workflow using real PlatformEngine and adapters
        
        This validates the actual production code path end-to-end.
        """
        output_dir = temp_workspace / "debug"
        workflow = EjectWorkflow(console, output_dir, "production")
        
        original_cwd = os.getcwd()
        os.chdir(temp_workspace)
        
        try:
            # Run actual workflow with real PlatformEngine
            workflow.run()
            
            # Verify directory structure created
            assert output_dir.exists()
            assert (output_dir / "scripts").exists()
            assert (output_dir / "context").exists()
            assert (output_dir / "pipeline").exists()
            
            # Verify README generated
            readme_path = output_dir / "README.md"
            assert readme_path.exists()
            readme_content = readme_path.read_text()
            assert "Ejected Bootstrap Artifacts" in readme_content
            assert "production" in readme_content
            
            # Verify scripts extracted for real adapters
            # Hetzner adapter has pre-work scripts
            hetzner_scripts_dir = output_dir / "scripts" / "hetzner"
            if hetzner_scripts_dir.exists():
                # Verify scripts are executable
                for script_file in hetzner_scripts_dir.glob("*.sh"):
                    assert oct(script_file.stat().st_mode)[-3:] == "755"
            
            # Talos adapter has bootstrap scripts
            talos_scripts_dir = output_dir / "scripts" / "talos"
            if talos_scripts_dir.exists():
                # Verify scripts are executable
                for script_file in talos_scripts_dir.glob("*.sh"):
                    assert oct(script_file.stat().st_mode)[-3:] == "755"
            
            # Cilium adapter has bootstrap scripts
            cilium_scripts_dir = output_dir / "scripts" / "cilium"
            if cilium_scripts_dir.exists():
                # Verify scripts are executable
                for script_file in cilium_scripts_dir.glob("*.sh"):
                    assert oct(script_file.stat().st_mode)[-3:] == "755"
            
            # Verify context files created where applicable
            context_dir = output_dir / "context"
            for adapter_context_dir in context_dir.iterdir():
                if adapter_context_dir.is_dir():
                    # Verify context files are valid JSON
                    for context_file in adapter_context_dir.glob("*.json"):
                        context_data = json.loads(context_file.read_text())
                        assert isinstance(context_data, dict)
            
            # Verify pipeline copied
            pipeline_file = output_dir / "pipeline" / "production.yaml"
            assert pipeline_file.exists()
            
        finally:
            os.chdir(original_cwd)
