"""Context managers for secure resource management."""

import atexit
import shutil
import signal
import tempfile
from pathlib import Path
from typing import Optional


class SecureTempDir:
    """Signal-safe temporary directory with guaranteed cleanup.
    
    Ensures cleanup on SIGINT/SIGTERM in addition to normal exit.
    Critical for security: prevents sensitive scripts from lingering in /tmp.
    """
    
    def __init__(self, prefix: str = "ztc-secure-"):
        self.prefix = prefix
        self.path: Optional[Path] = None
        self._cleanup_registered = False
        self._original_sigint_handler = None
        self._original_sigterm_handler = None
    
    def __enter__(self) -> Path:
        """Create secure temp directory with 0700 permissions."""
        self.path = Path(tempfile.mkdtemp(prefix=self.prefix))
        
        # Register cleanup with atexit (normal exit)
        if not self._cleanup_registered:
            atexit.register(self._cleanup)
            self._cleanup_registered = True
        
        # Register signal handlers (forced termination)
        self._original_sigint_handler = signal.signal(signal.SIGINT, self._signal_handler)
        self._original_sigterm_handler = signal.signal(signal.SIGTERM, self._signal_handler)
        
        return self.path
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup on normal context exit."""
        self._cleanup()
        self._restore_signal_handlers()
        return False
    
    def _cleanup(self):
        """Remove temporary directory (idempotent)."""
        if self.path and self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)
            self.path = None
    
    def _signal_handler(self, signum, frame):
        """Handle SIGINT/SIGTERM by cleaning up and re-raising."""
        self._cleanup()
        self._restore_signal_handlers()
        
        # Re-raise signal to allow normal signal handling
        if signum == signal.SIGINT:
            raise KeyboardInterrupt
        elif signum == signal.SIGTERM:
            raise SystemExit(128 + signum)
    
    def _restore_signal_handlers(self):
        """Restore original signal handlers."""
        if self._original_sigint_handler:
            signal.signal(signal.SIGINT, self._original_sigint_handler)
        if self._original_sigterm_handler:
            signal.signal(signal.SIGTERM, self._original_sigterm_handler)
