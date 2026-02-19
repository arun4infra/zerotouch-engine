"""Bootstrap executor - reads pipeline.yaml and executes stages"""

import yaml
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class StageResult:
    """Result from stage execution"""
    success: bool
    stage_name: str
    output: str
    error: Optional[str]
    cached: bool
    exit_code: int = 0


class BootstrapExecutor:
    """Execute bootstrap stages from pipeline.yaml"""
    
    def __init__(self, pipeline_path: Path):
        """Initialize executor
        
        Args:
            pipeline_path: Path to pipeline.yaml
        """
        self.pipeline_path = pipeline_path
        self.cache_file = Path(".zerotouch-cache/bootstrap-stage-cache.json")
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load pipeline
        with open(pipeline_path) as f:
            self.pipeline = yaml.safe_load(f)
        
        # Initialize cache
        if not self.cache_file.exists():
            self.cache_file.write_text('{"stages":{}}')
    
    def list_stages(self) -> List[Dict[str, Any]]:
        """List all stages from pipeline
        
        Returns:
            List of stage dicts with name, description, required
        """
        stages = []
        for stage in self.pipeline.get('stages', []):
            stages.append({
                'name': stage['name'],
                'description': stage.get('description', ''),
                'adapter': stage.get('adapter', ''),
                'required': stage.get('required', True),
                'cache_key': stage.get('cache_key')
            })
        return stages
    
    def get_stage_status(self, stage_name: str) -> str:
        """Get status of a stage
        
        Args:
            stage_name: Name of the stage
            
        Returns:
            Status: 'pending', 'cached', 'running', 'completed', 'failed'
        """
        # Check cache
        cache = self._load_cache()
        if stage_name in cache.get('stages', {}):
            return 'cached'
        return 'pending'
    
    async def execute_stage(self, stage_name: str, skip_cache: bool = False) -> StageResult:
        """Execute a single stage
        
        Args:
            stage_name: Name of the stage to execute
            skip_cache: Skip cache and re-execute
            
        Returns:
            StageResult with execution details
        """
        # Find stage in pipeline
        stage = None
        for s in self.pipeline.get('stages', []):
            if s['name'] == stage_name:
                stage = s
                break
        
        if not stage:
            return StageResult(
                success=False,
                stage_name=stage_name,
                output='',
                error=f"Stage '{stage_name}' not found in pipeline",
                cached=False
            )
        
        # Check cache
        cache_key = stage.get('cache_key')
        if cache_key and cache_key != 'null' and not skip_cache:
            if self._is_cached(cache_key):
                return StageResult(
                    success=True,
                    stage_name=stage_name,
                    output='Stage already completed (cached)',
                    error=None,
                    cached=True
                )
        
        # Check skip condition
        skip_if_empty = stage.get('skip_if_empty')
        if skip_if_empty:
            import os
            if not os.environ.get(skip_if_empty):
                return StageResult(
                    success=True,
                    stage_name=stage_name,
                    output=f'Skipped (condition: {skip_if_empty} is empty)',
                    error=None,
                    cached=False
                )
        
        # Get script path
        script = stage.get('script')
        if not script or script == 'null':
            return StageResult(
                success=True,
                stage_name=stage_name,
                output='No script to execute (pre-executed externally)',
                error=None,
                cached=False
            )
        
        # Build full script path
        script_path = Path('libs/workflow_engine/adapters') / script
        
        if not script_path.exists():
            if stage.get('required', True):
                return StageResult(
                    success=False,
                    stage_name=stage_name,
                    output='',
                    error=f"Required script not found: {script_path}",
                    cached=False
                )
            else:
                return StageResult(
                    success=True,
                    stage_name=stage_name,
                    output=f'Optional script not found: {script_path} (skipping)',
                    error=None,
                    cached=False
                )
        
        # Prepare environment (export platform.yaml data as env vars - legacy pattern)
        env = self._prepare_environment(stage)
        
        # Prepare environment (export platform.yaml data as env vars - legacy pattern)
        env = self._prepare_environment(stage)
        
        # Execute script
        try:
            # Build args and expand environment variables (legacy pattern)
            args = stage.get('args', [])
            expanded_args = []
            for arg in args:
                import os
                expanded_arg = os.path.expandvars(str(arg))
                expanded_args.append(expanded_arg)
            
            # Run script (with environment variables from platform.yaml)
            result = subprocess.run(
                ['bash', str(script_path)] + expanded_args,
                capture_output=True,
                text=True,
                timeout=stage.get('timeout', 600),
                env=env
            )
            
            if result.returncode == 0:
                # Mark as cached
                if cache_key and cache_key != 'null':
                    self._mark_cached(cache_key)
                
                return StageResult(
                    success=True,
                    stage_name=stage_name,
                    output=result.stdout,
                    error=None,
                    cached=False,
                    exit_code=result.returncode
                )
            else:
                return StageResult(
                    success=False,
                    stage_name=stage_name,
                    output=result.stdout,
                    error=result.stderr,
                    cached=False,
                    exit_code=result.returncode
                )
        
        except subprocess.TimeoutExpired:
            return StageResult(
                success=False,
                stage_name=stage_name,
                output='',
                error=f"Script timed out after {stage.get('timeout', 600)}s",
                cached=False
            )
        except Exception as e:
            return StageResult(
                success=False,
                stage_name=stage_name,
                output='',
                error=str(e),
                cached=False
            )
    
    async def rollback_stage(self, stage_name: str) -> bool:
        """Rollback a stage (remove from cache)
        
        Args:
            stage_name: Name of the stage
            
        Returns:
            True if successful
        """
        # Find stage cache_key
        stage = None
        for s in self.pipeline.get('stages', []):
            if s['name'] == stage_name:
                stage = s
                break
        
        if not stage:
            return False
        
        cache_key = stage.get('cache_key')
        if not cache_key or cache_key == 'null':
            return True  # Nothing to rollback
        
        # Remove from cache
        cache = self._load_cache()
        if cache_key in cache.get('stages', {}):
            del cache['stages'][cache_key]
            self._save_cache(cache)
        
        return True
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load cache from file"""
        if not self.cache_file.exists():
            return {'stages': {}}
        return json.loads(self.cache_file.read_text())
    
    def _save_cache(self, cache: Dict[str, Any]) -> None:
        """Save cache to file"""
        self.cache_file.write_text(json.dumps(cache, indent=2))
    
    def _is_cached(self, cache_key: str) -> bool:
        """Check if stage is cached"""
        cache = self._load_cache()
        return cache_key in cache.get('stages', {})
    
    def _mark_cached(self, cache_key: str) -> None:
        """Mark stage as cached"""
        cache = self._load_cache()
        cache['stages'][cache_key] = datetime.now().isoformat()
        self._save_cache(cache)
    
    def _prepare_environment(self, stage: dict) -> dict:
        """Prepare environment variables and context file from platform.yaml
        
        Creates ZTC_CONTEXT_FILE with adapter config (scripts expect this).
        Also exports common environment variables.
        """
        import os
        env = os.environ.copy()
        
        # Load platform.yaml
        platform_yaml = Path('platform/platform.yaml')
        if not platform_yaml.exists():
            return env
        
        import yaml
        with open(platform_yaml) as f:
            platform_data = yaml.safe_load(f)
        
        # Get adapter config for this stage
        adapter_name = stage.get('adapter')
        if not adapter_name:
            return env
        
        adapter_config = platform_data.get('adapters', {}).get(adapter_name, {})
        
        # Write context file (scripts expect ZTC_CONTEXT_FILE)
        context_file = Path('.zerotouch-cache/bootstrap-context.json')
        context_file.parent.mkdir(parents=True, exist_ok=True)
        context_file.write_text(json.dumps(adapter_config, indent=2))
        env['ZTC_CONTEXT_FILE'] = str(context_file.absolute())
        
        # Export common variables (uppercase, matching legacy pattern)
        env['MODE'] = 'production'
        env['ENV'] = 'dev'
        env['REPO_ROOT'] = str(Path.cwd())
        env['ARGOCD_NAMESPACE'] = 'argocd'
        
        # Export adapter-specific variables
        if adapter_name == 'talos':
            nodes = adapter_config.get('nodes', [])
            if nodes:
                for node in nodes:
                    if node.get('role') == 'controlplane':
                        env['SERVER_IP'] = node.get('ip', '')
                        break
            env['CLUSTER_NAME'] = adapter_config.get('cluster_name', '')
            env['CLUSTER_ENDPOINT'] = adapter_config.get('cluster_endpoint', '')
            # SSH_PASSWORD should come from user input or secrets file
            # For now, mark as TODO
            if 'SSH_PASSWORD' not in env:
                env['SSH_PASSWORD'] = ''  # Empty - script will fail with clear message
        
        elif adapter_name == 'hetzner':
            server_ips = adapter_config.get('server_ips', [])
            if server_ips:
                env['SERVER_IP'] = server_ips[0]
        
        return env
