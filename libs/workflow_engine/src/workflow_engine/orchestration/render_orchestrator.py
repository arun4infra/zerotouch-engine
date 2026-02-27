"""Render orchestrator - coordinates adapter rendering"""

from pathlib import Path
from typing import List, Optional, Callable
from dataclasses import dataclass

from workflow_engine.engine.engine import PlatformEngine


@dataclass
class RenderResult:
    """Result from render operation"""
    success: bool
    artifacts_path: Optional[Path] = None
    lock_file_path: Optional[Path] = None
    error: Optional[str] = None
    adapters_rendered: int = 0


class RenderOrchestrator:
    """Orchestrates adapter rendering workflow"""
    
    def __init__(self, platform_yaml_path: Path = Path("platform/platform.yaml")):
        """Initialize render orchestrator
        
        Args:
            platform_yaml_path: Path to platform.yaml
        """
        self.platform_yaml_path = platform_yaml_path
    
    async def render(
        self,
        partial: Optional[List[str]] = None,
        debug: bool = False,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> RenderResult:
        """Execute render workflow
        
        Args:
            partial: List of specific adapters to render (None = all)
            debug: Preserve workspace on failure
            progress_callback: Optional callback for progress updates
            
        Returns:
            RenderResult with operation details
        """
        try:
            # Create engine
            engine = PlatformEngine(self.platform_yaml_path, debug=debug)
            
            # Execute render
            await engine.render(partial=partial, progress_callback=progress_callback)
            
            # Count adapters
            adapters = engine.resolve_adapters(partial=partial)
            
            return RenderResult(
                success=True,
                artifacts_path=Path("platform/generated"),
                lock_file_path=Path("platform/lock.json"),
                adapters_rendered=len(adapters)
            )
        
        except FileNotFoundError as e:
            return RenderResult(
                success=False,
                error=f"Platform configuration not found: {e}"
            )
        except Exception as e:
            return RenderResult(
                success=False,
                error=str(e)
            )
