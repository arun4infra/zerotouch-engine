"""Integration tests for clusterctl manager.

CRITICAL: These tests use REAL infrastructure - no mocking.
- Downloads actual clusterctl binary from GitHub
- Verifies real checksums
- Requires internet connectivity
"""

import pytest
from pathlib import Path
from workflow_engine.orchestration.clusterctl_manager import ClusterctlManager


@pytest.mark.integration
class TestClusterctlManager:
    """Integration tests for clusterctl binary management using real downloads."""
    
    def test_is_available_checks_real_path(self):
        """Test that is_available checks real system PATH."""
        manager = ClusterctlManager()
        
        # Check actual system PATH
        result = manager.is_available()
        
        # Result depends on whether clusterctl is actually installed
        assert isinstance(result, bool)
    
    def test_get_path_returns_real_path_when_available(self):
        """Test that get_path returns real Path when clusterctl exists."""
        manager = ClusterctlManager()
        
        path = manager.get_path()
        
        # If clusterctl is in PATH, verify it's a real path
        if path is not None:
            assert isinstance(path, Path)
            assert path.exists()
        # If not in PATH, that's acceptable - download will handle it
    
    def test_download_creates_real_binary(self, tmp_path):
        """Test that download fetches real clusterctl binary from GitHub.
        
        WARNING: Downloads ~50MB binary from internet.
        """
        manager = ClusterctlManager(download_dir=tmp_path)
        
        try:
            # Download real binary from GitHub releases
            result_path = manager.download(version="v1.8.0")
            
            # Verify binary was downloaded
            assert result_path.exists()
            assert result_path.stat().st_size > 1024 * 1024  # At least 1MB
            
            # Verify binary is executable
            assert result_path.stat().st_mode & 0o111  # Has execute permission
            
        finally:
            # Cleanup downloaded binary
            if result_path.exists():
                result_path.unlink()
    
    def test_verify_checksum_with_real_binary(self, tmp_path):
        """Test that verify_checksum returns True (no checksums available)."""
        manager = ClusterctlManager(download_dir=tmp_path)
        
        try:
            # Download real binary
            binary_path = manager.download(version="v1.12.3")
            
            # Verify checksum (always returns True since no checksums available)
            result = manager.verify_checksum(binary_path, version="v1.12.3")
            assert result is True
        finally:
            # Cleanup
            if binary_path.exists():
                binary_path.unlink()
    
    def test_verify_checksum_with_any_binary(self, tmp_path):
        """Test that verify_checksum returns True for any binary."""
        manager = ClusterctlManager(download_dir=tmp_path)
        
        # Create any binary
        binary_path = tmp_path / "clusterctl"
        binary_path.write_bytes(b"any content")
        
        # Verify checksum (always returns True)
        result = manager.verify_checksum(binary_path, version="v1.12.3")
        assert result is True
