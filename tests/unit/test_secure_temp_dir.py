"""Tests for SecureTempDir context manager."""

import signal
import time
from pathlib import Path

import pytest

from ztc.utils.context_managers import SecureTempDir


def test_secure_temp_dir_creates_directory():
    """Test that SecureTempDir creates a directory with correct prefix."""
    with SecureTempDir(prefix="test-ztc-") as temp_path:
        assert temp_path.exists()
        assert temp_path.is_dir()
        assert "test-ztc-" in temp_path.name
        
        # Verify permissions (0700)
        stat_info = temp_path.stat()
        assert oct(stat_info.st_mode)[-3:] == "700"


def test_secure_temp_dir_cleanup_on_normal_exit():
    """Test that directory is cleaned up on normal context exit."""
    temp_path = None
    
    with SecureTempDir() as path:
        temp_path = path
        assert temp_path.exists()
    
    assert not temp_path.exists()


def test_secure_temp_dir_cleanup_on_exception():
    """Test that directory is cleaned up even when exception occurs."""
    temp_path = None
    
    try:
        with SecureTempDir() as path:
            temp_path = path
            assert temp_path.exists()
            raise ValueError("Test exception")
    except ValueError:
        pass
    
    assert not temp_path.exists()


def test_secure_temp_dir_idempotent_cleanup():
    """Test that cleanup can be called multiple times safely."""
    secure_dir = SecureTempDir()
    temp_path = secure_dir.__enter__()
    
    assert temp_path.exists()
    
    # Call cleanup multiple times
    secure_dir._cleanup()
    assert not temp_path.exists()
    
    secure_dir._cleanup()  # Should not raise
    secure_dir._cleanup()  # Should not raise


def test_secure_temp_dir_signal_handler_sigint():
    """Test that SIGINT triggers cleanup."""
    secure_dir = SecureTempDir()
    temp_path = secure_dir.__enter__()
    
    assert temp_path.exists()
    
    # Simulate SIGINT
    with pytest.raises(KeyboardInterrupt):
        secure_dir._signal_handler(signal.SIGINT, None)
    
    assert not temp_path.exists()


def test_secure_temp_dir_signal_handler_sigterm():
    """Test that SIGTERM triggers cleanup."""
    secure_dir = SecureTempDir()
    temp_path = secure_dir.__enter__()
    
    assert temp_path.exists()
    
    # Simulate SIGTERM
    with pytest.raises(SystemExit) as exc_info:
        secure_dir._signal_handler(signal.SIGTERM, None)
    
    assert exc_info.value.code == 128 + signal.SIGTERM
    assert not temp_path.exists()


def test_secure_temp_dir_restores_signal_handlers():
    """Test that original signal handlers are restored."""
    # Get current handlers
    original_sigint = signal.getsignal(signal.SIGINT)
    original_sigterm = signal.getsignal(signal.SIGTERM)
    
    with SecureTempDir() as temp_path:
        # Handlers should be replaced during context
        current_sigint = signal.getsignal(signal.SIGINT)
        current_sigterm = signal.getsignal(signal.SIGTERM)
        
        assert current_sigint != original_sigint
        assert current_sigterm != original_sigterm
    
    # Handlers should be restored after context exit
    restored_sigint = signal.getsignal(signal.SIGINT)
    restored_sigterm = signal.getsignal(signal.SIGTERM)
    
    assert restored_sigint == original_sigint
    assert restored_sigterm == original_sigterm


def test_secure_temp_dir_can_write_files():
    """Test that files can be written to the secure temp directory."""
    with SecureTempDir() as temp_path:
        test_file = temp_path / "test.txt"
        test_file.write_text("test content")
        
        assert test_file.exists()
        assert test_file.read_text() == "test content"
    
    assert not test_file.exists()
