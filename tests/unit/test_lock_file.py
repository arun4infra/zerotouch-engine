"""Unit tests for lock file generation and validation."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock

from ztc.engine.lock_file import LockFileGenerator
from ztc.commands.validate import ValidateCommand, LockFileValidationError


class TestLockFileGenerator:
    """Test lock file generation."""
    
    def test_hash_file(self, tmp_path):
        """Test file hashing with streaming."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        generator = LockFileGenerator(test_file)
        file_hash = generator.hash_file(test_file)
        
        # Verify hash is SHA256 hex digest
        assert len(file_hash) == 64
        assert all(c in "0123456789abcdef" for c in file_hash)
    
    def test_hash_file_large(self, tmp_path):
        """Test file hashing with large file (streaming)."""
        # Create large test file (> 8KB to test streaming)
        test_file = tmp_path / "large.txt"
        test_file.write_text("x" * 10000)
        
        generator = LockFileGenerator(test_file)
        file_hash = generator.hash_file(test_file)
        
        assert len(file_hash) == 64
    
    def test_hash_directory(self, tmp_path):
        """Test directory hashing with deterministic ordering."""
        # Create test directory structure
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file3.txt").write_text("content3")
        
        generator = LockFileGenerator(tmp_path / "platform.yaml")
        dir_hash = generator.hash_directory(tmp_path)
        
        # Verify hash is SHA256 hex digest
        assert len(dir_hash) == 64
        
        # Verify deterministic - same directory should produce same hash
        dir_hash2 = generator.hash_directory(tmp_path)
        assert dir_hash == dir_hash2
    
    def test_hash_directory_order_independent(self, tmp_path):
        """Test directory hashing is deterministic regardless of creation order."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        
        # Create files in different order
        (dir1 / "a.txt").write_text("content")
        (dir1 / "b.txt").write_text("content")
        
        (dir2 / "b.txt").write_text("content")
        (dir2 / "a.txt").write_text("content")
        
        generator = LockFileGenerator(tmp_path / "platform.yaml")
        hash1 = generator.hash_directory(dir1)
        hash2 = generator.hash_directory(dir2)
        
        # Hashes should be identical
        assert hash1 == hash2
    
    def test_generate_adapter_metadata(self, tmp_path):
        """Test adapter metadata generation."""
        # Create mock adapters
        adapter1 = Mock()
        adapter1.name = "hetzner"
        adapter1.phase = "foundation"
        adapter1.load_metadata.return_value = {"version": "1.0.0"}
        
        adapter2 = Mock()
        adapter2.name = "talos"
        adapter2.phase = "foundation"
        adapter2.load_metadata.return_value = {"version": "1.1.0"}
        
        generator = LockFileGenerator(tmp_path / "platform.yaml")
        metadata = generator.generate_adapter_metadata([adapter1, adapter2])
        
        assert metadata == {
            "hetzner": {"version": "1.0.0", "phase": "foundation"},
            "talos": {"version": "1.1.0", "phase": "foundation"}
        }
    
    def test_generate(self, tmp_path):
        """Test full lock file generation."""
        # Create test files
        platform_yaml = tmp_path / "platform.yaml"
        platform_yaml.write_text("test: config")
        
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "manifest.yaml").write_text("test: manifest")
        
        output_path = tmp_path / "lock.json"
        
        # Create mock adapter
        adapter = Mock()
        adapter.name = "test"
        adapter.phase = "foundation"
        adapter.load_metadata.return_value = {"version": "1.0.0"}
        
        generator = LockFileGenerator(platform_yaml, ztc_version="0.1.0")
        lock_data = generator.generate(artifacts_dir, [adapter], output_path)
        
        # Verify lock file structure
        assert "platform_hash" in lock_data
        assert "artifacts_hash" in lock_data
        assert lock_data["ztc_version"] == "0.1.0"
        assert "adapters" in lock_data
        assert lock_data["adapters"]["test"]["version"] == "1.0.0"
        
        # Verify file was written
        assert output_path.exists()
        written_data = json.loads(output_path.read_text())
        assert written_data == lock_data


class TestValidateCommand:
    """Test lock file validation."""
    
    @pytest.fixture
    def setup_repo(self, tmp_path, monkeypatch):
        """Setup test repository structure."""
        monkeypatch.chdir(tmp_path)
        
        # Create platform.yaml
        platform_yaml = tmp_path / "platform.yaml"
        platform_yaml.write_text("test: config")
        
        # Create artifacts directory
        artifacts_dir = tmp_path / "platform" / "generated"
        artifacts_dir.mkdir(parents=True)
        (artifacts_dir / "manifest.yaml").write_text("test: manifest")
        
        # Create lock file
        lock_file = tmp_path / "platform" / "lock.json"
        
        # Calculate hashes
        generator = LockFileGenerator(platform_yaml)
        platform_hash = generator.hash_file(platform_yaml)
        artifacts_hash = generator.hash_directory(artifacts_dir)
        
        lock_data = {
            "platform_hash": platform_hash,
            "artifacts_hash": artifacts_hash,
            "ztc_version": "0.1.0",
            "adapters": {}
        }
        lock_file.write_text(json.dumps(lock_data))
        
        return tmp_path
    
    def test_validate_success(self, setup_repo):
        """Test validation passes with valid lock file."""
        cmd = ValidateCommand()
        cmd.execute()  # Should not raise
    
    def test_validate_lock_file_not_found(self, tmp_path, monkeypatch):
        """Test validation fails when lock file doesn't exist."""
        monkeypatch.chdir(tmp_path)
        
        cmd = ValidateCommand()
        
        with pytest.raises(LockFileValidationError) as exc_info:
            cmd.execute()
        
        assert "Lock file not found" in str(exc_info.value)
    
    def test_validate_platform_modified(self, setup_repo):
        """Test validation fails when platform.yaml is modified."""
        # Modify platform.yaml
        platform_yaml = setup_repo / "platform.yaml"
        platform_yaml.write_text("modified: config")
        
        cmd = ValidateCommand()
        
        with pytest.raises(LockFileValidationError) as exc_info:
            cmd.execute()
        
        assert "has been modified" in str(exc_info.value)
    
    def test_validate_artifacts_modified(self, setup_repo):
        """Test validation fails when artifacts are modified."""
        # Modify artifacts
        artifacts_dir = setup_repo / "platform" / "generated"
        (artifacts_dir / "new_file.yaml").write_text("new: content")
        
        cmd = ValidateCommand()
        
        with pytest.raises(LockFileValidationError) as exc_info:
            cmd.execute()
        
        assert "artifacts have been modified" in str(exc_info.value)
    
    def test_validate_artifacts_not_found(self, tmp_path, monkeypatch):
        """Test validation fails when artifacts directory doesn't exist."""
        monkeypatch.chdir(tmp_path)
        
        # Create minimal setup without artifacts
        platform_yaml = tmp_path / "platform.yaml"
        platform_yaml.write_text("test: config")
        
        # Calculate correct platform hash
        generator = LockFileGenerator(platform_yaml)
        platform_hash = generator.hash_file(platform_yaml)
        
        lock_file = tmp_path / "platform" / "lock.json"
        lock_file.parent.mkdir(parents=True)
        lock_file.write_text(json.dumps({
            "platform_hash": platform_hash,
            "artifacts_hash": "dummy"
        }))
        
        cmd = ValidateCommand()
        
        with pytest.raises(LockFileValidationError) as exc_info:
            cmd.execute()
        
        assert "Artifacts directory not found" in str(exc_info.value)
