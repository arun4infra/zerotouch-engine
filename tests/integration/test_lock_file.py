"""Integration tests for lock file generation and validation."""

import json
import pytest
from pathlib import Path
import os

from ztc.engine.lock_file import LockFileGenerator
from ztc.commands.validate import ValidateCommand, LockFileValidationError
from ztc.adapters.hetzner.adapter import HetznerAdapter
from ztc.adapters.talos.adapter import TalosAdapter
from ztc.adapters.cilium.adapter import CiliumAdapter


class TestLockFileIntegration:
    """Integration tests for lock file system."""
    
    @pytest.fixture
    def temp_workspace(self, tmp_path):
        """Create temporary workspace with platform.yaml."""
        # Create platform.yaml
        platform_yaml = tmp_path / "platform.yaml"
        platform_yaml.write_text("""
adapters:
  hetzner:
    version: "1.0.0"
    api_token: "test-token"
    server_ips:
      - "192.168.1.1"
  talos:
    version: "1.11.5"
    cluster_name: "test-cluster"
    cluster_endpoint: "192.168.1.1:6443"
    nodes:
      - name: "cp01"
        ip: "192.168.1.1"
        role: "controlplane"
  cilium:
    version: "1.18.5"
    bgp:
      enabled: false
""")
        
        # Create artifacts directory
        artifacts_dir = tmp_path / "platform" / "generated"
        artifacts_dir.mkdir(parents=True)
        
        # Create some test artifacts
        (artifacts_dir / "network").mkdir()
        (artifacts_dir / "network" / "cilium").mkdir()
        (artifacts_dir / "network" / "cilium" / "manifests.yaml").write_text("test: manifest")
        
        (artifacts_dir / "os").mkdir()
        (artifacts_dir / "os" / "talos").mkdir()
        (artifacts_dir / "os" / "talos" / "config.yaml").write_text("test: config")
        
        return tmp_path
    
    def test_lock_file_generation_and_validation(self, temp_workspace):
        """Test lock file is generated after render and validates correctly."""
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_workspace)
            
            platform_yaml = temp_workspace / "platform.yaml"
            artifacts_dir = temp_workspace / "platform" / "generated"
            lock_path = temp_workspace / "platform" / "lock.json"
            
            # Use real production adapters
            hetzner_config = {
                "api_token": "test-token",
                "server_ips": ["192.168.1.1"]
            }
            hetzner_adapter = HetznerAdapter(hetzner_config)
            
            talos_config = {
                "cluster_name": "test-cluster",
                "cluster_endpoint": "192.168.1.1:6443",
                "nodes": [
                    {"name": "cp01", "ip": "192.168.1.1", "role": "controlplane"}
                ]
            }
            talos_adapter = TalosAdapter(talos_config)
            
            cilium_config = {
                "bgp": {"enabled": False}
            }
            cilium_adapter = CiliumAdapter(cilium_config)
            
            adapters = [hetzner_adapter, talos_adapter, cilium_adapter]
            
            # Generate lock file using production LockFileGenerator
            generator = LockFileGenerator(platform_yaml, ztc_version="0.1.0")
            lock_data = generator.generate(artifacts_dir, adapters, lock_path)
            
            # Verify lock file structure
            assert lock_path.exists()
            assert "platform_hash" in lock_data
            assert "artifacts_hash" in lock_data
            assert lock_data["ztc_version"] == "0.1.0"
            assert "adapters" in lock_data
            assert "hetzner" in lock_data["adapters"]
            assert "talos" in lock_data["adapters"]
            assert "cilium" in lock_data["adapters"]
            
            # Validate lock file using production ValidateCommand
            validate_cmd = ValidateCommand()
            validate_cmd.execute()  # Should not raise
            
        finally:
            os.chdir(original_cwd)
    
    def test_lock_file_detects_platform_modifications(self, temp_workspace):
        """Test lock file validation detects platform.yaml modifications."""
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_workspace)
            
            platform_yaml = temp_workspace / "platform.yaml"
            artifacts_dir = temp_workspace / "platform" / "generated"
            lock_path = temp_workspace / "platform" / "lock.json"
            
            # Use real production adapter
            hetzner_config = {
                "api_token": "test-token",
                "server_ips": ["192.168.1.1"]
            }
            hetzner_adapter = HetznerAdapter(hetzner_config)
            
            # Generate lock file using production classes
            generator = LockFileGenerator(platform_yaml, ztc_version="0.1.0")
            generator.generate(artifacts_dir, [hetzner_adapter], lock_path)
            
            # Modify platform.yaml
            platform_yaml.write_text("modified: config")
            
            # Validation should fail using production ValidateCommand
            validate_cmd = ValidateCommand()
            with pytest.raises(LockFileValidationError) as exc_info:
                validate_cmd.execute()
            
            assert "has been modified" in str(exc_info.value)
            
        finally:
            os.chdir(original_cwd)
    
    def test_lock_file_detects_artifact_modifications(self, temp_workspace):
        """Test lock file validation detects artifact modifications."""
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_workspace)
            
            platform_yaml = temp_workspace / "platform.yaml"
            artifacts_dir = temp_workspace / "platform" / "generated"
            lock_path = temp_workspace / "platform" / "lock.json"
            
            # Use real production adapter
            talos_config = {
                "cluster_name": "test-cluster",
                "cluster_endpoint": "192.168.1.1:6443",
                "nodes": [
                    {"name": "cp01", "ip": "192.168.1.1", "role": "controlplane"}
                ]
            }
            talos_adapter = TalosAdapter(talos_config)
            
            # Generate lock file using production classes
            generator = LockFileGenerator(platform_yaml, ztc_version="0.1.0")
            generator.generate(artifacts_dir, [talos_adapter], lock_path)
            
            # Modify artifacts
            (artifacts_dir / "new_file.yaml").write_text("new: content")
            
            # Validation should fail using production ValidateCommand
            validate_cmd = ValidateCommand()
            with pytest.raises(LockFileValidationError) as exc_info:
                validate_cmd.execute()
            
            assert "artifacts have been modified" in str(exc_info.value)
            
        finally:
            os.chdir(original_cwd)
    
    def test_streaming_hash_handles_large_files(self, temp_workspace):
        """Test streaming hash handles large files without memory issues."""
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_workspace)
            
            platform_yaml = temp_workspace / "platform.yaml"
            artifacts_dir = temp_workspace / "platform" / "generated"
            
            # Create large file (10MB)
            large_file = artifacts_dir / "large_manifest.yaml"
            large_file.write_text("x" * (10 * 1024 * 1024))
            
            # Generate lock file with large file using production LockFileGenerator
            generator = LockFileGenerator(platform_yaml)
            artifacts_hash = generator.hash_directory(artifacts_dir)
            
            # Verify hash is generated
            assert len(artifacts_hash) == 64
            
        finally:
            os.chdir(original_cwd)

