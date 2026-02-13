"""Integration tests for bootstrap preparation using real production code paths

Uses actual BootstrapCommand, VacuumCommand, and SecureTempDir.
No mocking of internal components per integration testing patterns.
"""

import json
import tempfile
from pathlib import Path
import shutil
import os

import pytest
import yaml

from ztc.commands.bootstrap import (
    BootstrapCommand,
    BootstrapError,
    EnvironmentMismatchError,
    LockFileNotFoundError,
    PlatformModifiedError,
    RuntimeDependencyError,
)
from ztc.utils.context_managers import SecureTempDir
from ztc.utils.vacuum import VacuumCommand
from rich.console import Console


class TestBootstrapPreparation:
    """Test bootstrap preparation with real production code paths"""
    
    @pytest.fixture
    def temp_repo(self):
        """Create temporary repository structure with real config"""
        temp_dir = tempfile.mkdtemp()
        repo = Path(temp_dir)
        
        # Create platform.yaml with real adapter config
        platform_yaml = repo / "platform.yaml"
        config = {
            "hetzner": {
                "version": "v1.0.0",
                "api_token": "a" * 64,
                "server_ips": ["192.168.1.1"],
                "rescue_mode_confirm": True
            },
            "talos": {
                "version": "v1.11.5",
                "factory_image_id": "test-factory-id",
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
        
        # Create lock file
        lock_dir = repo / "platform"
        lock_dir.mkdir()
        lock_file = lock_dir / "lock.json"
        
        import hashlib
        platform_hash = hashlib.sha256(platform_yaml.read_bytes()).hexdigest()
        
        lock_file.write_text(json.dumps({
            "environment": "production",
            "platform_hash": platform_hash,
            "ztc_version": "0.1.0",
            "adapters": {
                "hetzner": {"version": "v1.0.0"},
                "talos": {"version": "v1.11.5"}
            }
        }))
        
        # Create pipeline directory
        pipeline_dir = repo / "bootstrap" / "pipeline"
        pipeline_dir.mkdir(parents=True)
        pipeline_yaml = pipeline_dir / "production.yaml"
        pipeline_yaml.write_text(yaml.dump({
            "stages": [
                {
                    "name": "test_stage",
                    "script": "talos://install.sh",
                    "description": "Test stage"
                }
            ]
        }))
        
        yield repo
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def console(self):
        """Real Rich console"""
        return Console()
    
    def test_bootstrap_command_creation(self):
        """Test BootstrapCommand instantiation with real parameters"""
        cmd = BootstrapCommand("production", skip_cache=False)
        
        assert cmd.env == "production"
        assert cmd.skip_cache == False
        assert cmd.repo_root == Path.cwd()
    
    def test_validate_lock_file_not_found(self, temp_repo):
        """Test lock file validation fails when file doesn't exist"""
        cmd = BootstrapCommand("production")
        cmd.repo_root = temp_repo
        
        # Remove lock file
        (temp_repo / "platform" / "lock.json").unlink()
        
        with pytest.raises(LockFileNotFoundError) as exc_info:
            cmd.validate_lock_file()
        
        assert "Lock file not found" in str(exc_info.value)
    
    def test_validate_lock_file_environment_mismatch(self, temp_repo):
        """Test lock file validation fails on environment mismatch"""
        cmd = BootstrapCommand("staging")
        cmd.repo_root = temp_repo
        
        with pytest.raises(EnvironmentMismatchError) as exc_info:
            cmd.validate_lock_file()
        
        assert "does not match" in str(exc_info.value)
    
    def test_validate_lock_file_platform_modified(self, temp_repo):
        """Test lock file validation fails when platform.yaml is modified"""
        cmd = BootstrapCommand("production")
        cmd.repo_root = temp_repo
        
        # Modify platform.yaml
        platform_yaml = temp_repo / "platform.yaml"
        platform_yaml.write_text(yaml.dump({"modified": "content"}))
        
        with pytest.raises(PlatformModifiedError) as exc_info:
            cmd.validate_lock_file()
        
        assert "has been modified" in str(exc_info.value)
    
    def test_validate_lock_file_success(self, temp_repo):
        """Test lock file validation passes with valid config"""
        cmd = BootstrapCommand("production")
        cmd.repo_root = temp_repo
        
        # Should not raise
        cmd.validate_lock_file()
    
    def test_prepare_env_vars_with_real_config(self, temp_repo):
        """Test environment variable preparation with real adapter config"""
        cmd = BootstrapCommand("production")
        cmd.repo_root = temp_repo
        
        env_vars = cmd.prepare_env_vars()
        
        assert env_vars["ENV"] == "production"
        assert env_vars["REPO_ROOT"] == str(temp_repo)
        
        # Verify adapter-specific env vars are created
        assert "HETZNER_API_TOKEN" in env_vars
        assert env_vars["HETZNER_API_TOKEN"] == "a" * 64
    
    def test_resolve_context_vars_with_real_env(self):
        """Test context variable resolution with real environment"""
        cmd = BootstrapCommand("production")
        
        # Set real environment variable
        os.environ["TEST_VAR"] = "test_value"
        
        try:
            context_data = {
                "simple": "$TEST_VAR",
                "braces": "${TEST_VAR}",
                "nested": {
                    "key": "$TEST_VAR"
                },
                "list": ["$TEST_VAR", "static"]
            }
            
            resolved = cmd._resolve_context_vars(context_data)
            
            assert resolved["simple"] == "test_value"
            assert resolved["braces"] == "test_value"
            assert resolved["nested"]["key"] == "test_value"
            assert resolved["list"][0] == "test_value"
            assert resolved["list"][1] == "static"
        finally:
            del os.environ["TEST_VAR"]
    
    def test_secure_temp_dir_creates_and_cleans(self):
        """Test SecureTempDir creates secure directory and cleans up"""
        with SecureTempDir() as temp_path:
            assert temp_path.exists()
            assert temp_path.is_dir()
            
            # Verify permissions are secure (0700)
            assert oct(temp_path.stat().st_mode)[-3:] == "700"
            
            temp_path_str = str(temp_path)
        
        # After context exit, directory should be cleaned up
        assert not Path(temp_path_str).exists()
    
    def test_secure_temp_dir_cleanup_on_exception(self):
        """Test SecureTempDir cleans up even on exception"""
        temp_path_str = None
        
        try:
            with SecureTempDir() as temp_path:
                temp_path_str = str(temp_path)
                assert temp_path.exists()
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Directory should still be cleaned up
        assert not Path(temp_path_str).exists()
    
    def test_vacuum_command_finds_stale_directories(self, console):
        """Test VacuumCommand finds stale directories"""
        vacuum = VacuumCommand(console, max_age_minutes=0)
        
        # Create a stale directory
        temp_dir = tempfile.mkdtemp(prefix="ztc-secure-")
        temp_path = Path(temp_dir)
        
        try:
            # Make it appear old
            import time
            old_time = time.time() - 120  # 2 minutes ago
            os.utime(temp_path, (old_time, old_time))
            
            stale_dirs = vacuum.find_stale_directories()
            
            # Should find the directory
            assert len(stale_dirs) > 0
            assert any(d["path"].name.startswith("ztc-secure-") for d in stale_dirs)
        finally:
            if temp_path.exists():
                shutil.rmtree(temp_path)
    
    def test_vacuum_command_ignores_recent_directories(self, console):
        """Test VacuumCommand ignores recent directories"""
        vacuum = VacuumCommand(console, max_age_minutes=60)
        
        # Create a recent directory
        temp_dir = tempfile.mkdtemp(prefix="ztc-secure-")
        temp_path = Path(temp_dir)
        
        try:
            stale_dirs = vacuum.find_stale_directories()
            
            # Should not find the recent directory
            assert not any(d["path"] == temp_path for d in stale_dirs)
        finally:
            if temp_path.exists():
                shutil.rmtree(temp_path)
    
    def test_vacuum_command_execute_removes_stale_dirs(self, console):
        """Test VacuumCommand execute removes stale directories"""
        vacuum = VacuumCommand(console, max_age_minutes=0)
        
        # Create a stale directory
        temp_dir = tempfile.mkdtemp(prefix="ztc-secure-")
        temp_path = Path(temp_dir)
        
        # Make it appear old
        import time
        old_time = time.time() - 120  # 2 minutes ago
        os.utime(temp_path, (old_time, old_time))
        
        # Execute vacuum
        vacuum.execute()
        
        # Directory should be removed
        assert not temp_path.exists()
