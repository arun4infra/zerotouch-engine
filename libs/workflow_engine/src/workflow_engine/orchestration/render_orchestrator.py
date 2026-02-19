"""Render workflow orchestrator."""

from pathlib import Path
from typing import Optional, List, Callable
from workflow_engine.engine.engine import PlatformEngine
from workflow_engine.services.platform_config_service import PlatformConfigService


class RenderOrchestrator:
    """Orchestrates render workflow."""
    
    def __init__(self, config_service: Optional[PlatformConfigService] = None):
        self.config_service = config_service or PlatformConfigService()
    
    async def render(
        self,
        partial: Optional[List[str]] = None,
        debug: bool = False,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> dict:
        """Execute render workflow.
        
        Args:
            partial: List of adapter names to render (None = all)
            debug: Keep workspace on failure
            progress_callback: Optional callback for progress updates
            
        Returns:
            dict with success status and any error message
        """
        try:
            # Load platform config
            if not self.config_service.exists():
                return {
                    "success": False,
                    "error": "platform.yaml not found. Run 'ztc init' first."
                }
            
            # Create engine with platform.yaml path
            platform_yaml_path = Path("platform/platform.yaml")
            engine = PlatformEngine(platform_yaml_path, debug=debug)
            
            # Execute render
            await engine.render(partial=partial, progress_callback=progress_callback)
            
            return {"success": True}
            
        except Exception as e:
            if debug:
                if progress_callback:
                    progress_callback(f"Error: {e}. Workspace preserved at .zerotouch-cache/workspace")
            return {
                "success": False,
                "error": str(e)
            }
