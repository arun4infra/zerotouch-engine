"""Bootstrap orchestrator - coordinates pipeline execution"""

import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from workflow_engine.engine.bootstrap_executor import BootstrapExecutor, StageResult
from workflow_engine.engine.bootstrap_pipeline import generate_bootstrap_pipeline


@dataclass
class BootstrapResult:
    """Result from bootstrap operation"""
    success: bool
    stages_executed: int = 0
    stages_cached: int = 0
    error: Optional[str] = None
    failed_stage: Optional[str] = None


class BootstrapOrchestrator:
    """Orchestrates bootstrap pipeline execution"""
    
    def __init__(
        self, 
        pipeline_yaml_path: Path = Path("platform/pipeline.yaml"),
        platform_yaml_path: Path = Path("platform/platform.yaml")
    ):
        """Initialize bootstrap orchestrator
        
        Args:
            pipeline_yaml_path: Path to pipeline.yaml
            platform_yaml_path: Path to platform.yaml
        """
        self.pipeline_yaml_path = pipeline_yaml_path
        self.platform_yaml_path = platform_yaml_path
        
        # Generate pipeline.yaml if it doesn't exist
        if not self.pipeline_yaml_path.exists():
            if self.platform_yaml_path.exists():
                generate_bootstrap_pipeline(self.platform_yaml_path, self.pipeline_yaml_path)
    
    def list_stages(self) -> List[Dict[str, Any]]:
        """List all stages in pipeline
        
        Returns:
            List of stage dicts with name, description, required
        """
        # Ensure pipeline exists before listing
        if not self.pipeline_yaml_path.exists():
            if self.platform_yaml_path.exists():
                generate_bootstrap_pipeline(self.platform_yaml_path, self.pipeline_yaml_path)
        
        try:
            executor = BootstrapExecutor(self.pipeline_yaml_path)
            return executor.list_stages()
        except Exception:
            return []
    
    async def execute(self, skip_cache: bool = False, progress_callback=None) -> BootstrapResult:
        """Execute bootstrap pipeline
        
        Args:
            skip_cache: Skip cache and re-execute all stages
            progress_callback: Optional callback for progress updates
                              Signature: callback(stage_name, status, message)
                              status: 'start' | 'success' | 'cached' | 'failed'
            
        Returns:
            BootstrapResult with execution details
        """
        # Clean up logs from previous runs
        log_dir = Path('.zerotouch-cache/logs/bootstrap')
        if log_dir.exists():
            import shutil
            shutil.rmtree(log_dir)
        
        # Ensure pipeline exists
        if not self.pipeline_yaml_path.exists():
            if self.platform_yaml_path.exists():
                generate_bootstrap_pipeline(self.platform_yaml_path, self.pipeline_yaml_path)
        
        try:
            executor = BootstrapExecutor(self.pipeline_yaml_path)
            stages = executor.list_stages()
            
            if not stages:
                return BootstrapResult(
                    success=True,
                    stages_executed=0,
                    stages_cached=0
                )
            
            executed = 0
            cached = 0
            
            for stage in stages:
                stage_name = stage['name']
                
                # Notify start
                if progress_callback:
                    progress_callback(stage_name, 'start', stage.get('description', ''))
                
                # Execute stage
                result = await executor.execute_stage(stage_name, skip_cache=skip_cache)
                
                if not result.success:
                    # Notify failure
                    if progress_callback:
                        progress_callback(stage_name, 'failed', result.error or '')
                    
                    return BootstrapResult(
                        success=False,
                        stages_executed=executed,
                        stages_cached=cached,
                        error=result.error,
                        failed_stage=stage_name
                    )
                
                # Update counters
                if result.cached:
                    cached += 1
                    if progress_callback:
                        progress_callback(stage_name, 'cached', '')
                else:
                    executed += 1
                    if progress_callback:
                        progress_callback(stage_name, 'success', '')
            
            return BootstrapResult(
                success=True,
                stages_executed=executed,
                stages_cached=cached
            )
        
        except FileNotFoundError as e:
            return BootstrapResult(
                success=False,
                error=f"Pipeline not found: {e}"
            )
        except Exception as e:
            return BootstrapResult(
                success=False,
                error=str(e)
            )
    
    async def execute_stage(self, stage_name: str, skip_cache: bool = False) -> StageResult:
        """Execute a single stage
        
        Args:
            stage_name: Name of the stage to execute
            skip_cache: Skip cache and re-execute
            
        Returns:
            StageResult with execution details
        """
        executor = BootstrapExecutor(self.pipeline_yaml_path)
        return await executor.execute_stage(stage_name, skip_cache=skip_cache)
