"""Vacuum command for cleaning up stale temporary directories."""

import shutil
import tempfile
import time
from pathlib import Path
from typing import Dict, List

from rich.console import Console
from rich.table import Table


class VacuumCommand:
    """Clean up stale temporary directories from crashed runs.
    
    Handles SIGKILL (9) scenarios where SecureTempDir cleanup couldn't run.
    Provides a safety net for sensitive data left in /tmp after hard crashes.
    """
    
    def __init__(self, console: Console, max_age_minutes: int = 60):
        self.console = console
        self.max_age_minutes = max_age_minutes
        self.temp_root = Path(tempfile.gettempdir())
    
    def execute(self):
        """Find and remove stale ztc-secure-* directories."""
        stale_dirs = self.find_stale_directories()
        
        if not stale_dirs:
            self.console.print("[green]✓[/green] No stale temporary directories found")
            return
        
        # Display findings
        table = Table(title="Stale Temporary Directories")
        table.add_column("Directory", style="yellow")
        table.add_column("Age (minutes)", style="cyan")
        table.add_column("Size", style="magenta")
        
        for dir_info in stale_dirs:
            table.add_row(
                dir_info["path"].name,
                str(dir_info["age_minutes"]),
                self.format_size(dir_info["size_bytes"])
            )
        
        self.console.print(table)
        
        # Clean up
        removed_count = 0
        for dir_info in stale_dirs:
            try:
                shutil.rmtree(dir_info["path"], ignore_errors=True)
                removed_count += 1
            except Exception as e:
                self.console.print(
                    f"[yellow]⚠[/yellow] Failed to remove {dir_info['path'].name}: {e}"
                )
        
        self.console.print(
            f"[green]✓[/green] Removed {removed_count}/{len(stale_dirs)} stale directories"
        )
    
    def find_stale_directories(self) -> List[Dict]:
        """Find ztc-secure-* directories older than max_age_minutes."""
        stale_dirs = []
        current_time = time.time()
        cutoff_time = current_time - (self.max_age_minutes * 60)
        
        # Search for ztc-secure-* directories in temp root
        for path in self.temp_root.glob("ztc-secure-*"):
            if not path.is_dir():
                continue
            
            # Check modification time (last activity)
            mtime = path.stat().st_mtime
            
            if mtime < cutoff_time:
                age_minutes = int((current_time - mtime) / 60)
                size_bytes = self.get_directory_size(path)
                
                stale_dirs.append({
                    "path": path,
                    "age_minutes": age_minutes,
                    "size_bytes": size_bytes
                })
        
        return stale_dirs
    
    def get_directory_size(self, path: Path) -> int:
        """Calculate total size of directory in bytes."""
        total_size = 0
        try:
            for item in path.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
        except Exception:
            pass  # Ignore permission errors
        return total_size
    
    def format_size(self, size_bytes: int) -> str:
        """Format bytes as human-readable size."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
