"""Lock file generation for ZTC render pipeline.

This module provides lock file generation to prevent drift between render and bootstrap.
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, Any, List

from ztc.adapters.base import PlatformAdapter


class LockFileGenerator:
    """Generate lock files to prevent drift between render and bootstrap.
    
    Lock files contain:
    - platform_hash: SHA256 of platform.yaml
    - artifacts_hash: SHA256 of generated artifacts directory
    - ztc_version: CLI version used for render
    - adapters: Metadata for each adapter (version, phase)
    """
    
    def __init__(self, platform_yaml: Path, ztc_version: str = "1.0.0"):
        """Initialize lock file generator.
        
        Args:
            platform_yaml: Path to platform.yaml
            ztc_version: ZTC CLI version
        """
        self.platform_yaml = platform_yaml
        self.ztc_version = ztc_version
    
    def generate(
        self,
        artifacts_dir: Path,
        adapters: List[PlatformAdapter],
        output_path: Path
    ) -> Dict[str, Any]:
        """Generate lock file with artifact hashes and adapter metadata.
        
        Args:
            artifacts_dir: Path to generated artifacts directory
            adapters: List of adapters that were rendered
            output_path: Path where lock file should be written
            
        Returns:
            Lock file data structure
        """
        # Calculate platform.yaml hash
        platform_hash = self.hash_file(self.platform_yaml)
        
        # Calculate artifacts directory hash
        artifacts_hash = self.hash_directory(artifacts_dir)
        
        # Build adapter metadata
        adapter_metadata = self.generate_adapter_metadata(adapters)
        
        # Create lock file structure
        lock_data = {
            "platform_hash": platform_hash,
            "artifacts_hash": artifacts_hash,
            "ztc_version": self.ztc_version,
            "adapters": adapter_metadata
        }
        
        # Write lock file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(lock_data, f, indent=2)
        
        return lock_data
    
    def hash_file(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file with streaming.
        
        Uses streaming to handle large files without memory issues.
        
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
        """Calculate hash of directory contents with streaming.
        
        Uses streaming to handle large files without memory issues.
        Sorts files for deterministic hashing.
        
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
                
                # Hash file content with streaming
                file_hash = self.hash_file(file_path)
                sha256.update(file_hash.encode())
        
        return sha256.hexdigest()
    
    def generate_adapter_metadata(self, adapters: List[PlatformAdapter]) -> Dict[str, Dict[str, str]]:
        """Generate metadata for each adapter.
        
        Args:
            adapters: List of adapters that were rendered
            
        Returns:
            Dictionary mapping adapter name to metadata
        """
        adapter_metadata = {}
        for adapter in adapters:
            metadata = adapter.load_metadata()
            adapter_metadata[adapter.name] = {
                "version": metadata.get("version", "unknown"),
                "phase": adapter.phase
            }
        return adapter_metadata
