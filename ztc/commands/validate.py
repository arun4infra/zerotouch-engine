"""Validate command for lock file validation."""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any


class LockFileValidationError(Exception):
    """Raised when lock file validation fails."""
    pass


class ValidateCommand:
    """Validate generated artifacts against lock file."""
    
    def __init__(self):
        self.repo_root = Path.cwd()
        platform_yaml = self.repo_root / "platform" / "platform.yaml"
        if not platform_yaml.exists():
            platform_yaml = self.repo_root / "platform.yaml"  # Fallback
        self.platform_yaml = platform_yaml
        self.lock_file = self.repo_root / "platform" / "lock.json"
        self.artifacts_dir = self.repo_root / "platform" / "generated"
    
    def execute(self):
        """Execute validation checks."""
        # Check lock file exists
        if not self.lock_file.exists():
            raise LockFileValidationError(
                "Lock file not found. Run 'ztc render' to generate artifacts."
            )
        
        # Load lock file
        lock_data = json.loads(self.lock_file.read_text())
        
        # Validate platform.yaml hash
        self.validate_platform_hash(lock_data)
        
        # Validate artifacts hash
        self.validate_artifacts_hash(lock_data)
    
    def validate_platform_hash(self, lock_data: Dict[str, Any]):
        """Validate platform.yaml hash matches lock file.
        
        Args:
            lock_data: Lock file data
            
        Raises:
            LockFileValidationError: If hash mismatch detected
        """
        if not self.platform_yaml.exists():
            raise LockFileValidationError("platform.yaml not found")
        
        current_hash = self.hash_file(self.platform_yaml)
        expected_hash = lock_data.get("platform_hash")
        
        if current_hash != expected_hash:
            raise LockFileValidationError(
                "platform.yaml has been modified since render. "
                "Run 'ztc render' to regenerate artifacts."
            )
    
    def validate_artifacts_hash(self, lock_data: Dict[str, Any]):
        """Validate artifacts directory hash matches lock file.
        
        Args:
            lock_data: Lock file data
            
        Raises:
            LockFileValidationError: If hash mismatch detected
        """
        if not self.artifacts_dir.exists():
            raise LockFileValidationError(
                "Artifacts directory not found. Run 'ztc render' to generate artifacts."
            )
        
        current_hash = self.hash_directory(self.artifacts_dir)
        expected_hash = lock_data.get("artifacts_hash")
        
        if current_hash != expected_hash:
            raise LockFileValidationError(
                "Generated artifacts have been modified. "
                "Run 'ztc render' to regenerate artifacts."
            )
    
    def hash_file(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Hex digest of file hash
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def hash_directory(self, directory: Path) -> str:
        """Calculate hash of directory contents.
        
        Args:
            directory: Path to directory
            
        Returns:
            Hex digest of directory hash
        """
        sha256 = hashlib.sha256()
        
        # Sort files for deterministic hashing
        files = sorted(directory.rglob("*"))
        
        for file_path in files:
            if file_path.is_file():
                # Hash file path relative to directory
                rel_path = file_path.relative_to(directory)
                sha256.update(str(rel_path).encode())
                
                # Hash file content directly (must match engine implementation)
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        sha256.update(chunk)
        
        return sha256.hexdigest()
