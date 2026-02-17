"""Bootstrap stage execution with caching and barriers"""

import subprocess
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass
class StageResult:
    """Result from stage execution"""
    status: str  # "success", "failed", "cached"
    stage_name: str
    cached: bool
    duration_seconds: float
    exit_code: int
    stdout: str
    stderr: str
    error: Optional[str] = None


class BootstrapExecutor:
    """Execute bootstrap stages with caching and barriers"""
    
    def __init__(self, cache_dir: Path = None, skip_cache: bool = False):
        """Initialize bootstrap executor
        
        Args:
            cache_dir: Directory for stage cache (default: .zerotouch-cache/stage-cache)
            skip_cache: Skip cache and re-execute all stages
        """
        self.cache_dir = cache_dir or Path(".zerotouch-cache/stage-cache")
        self.skip_cache = skip_cache
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def is_stage_cached(self, cache_key: str) -> bool:
        """Check if stage is cached
        
        Args:
            cache_key: Unique key for the stage
            
        Returns:
            True if stage is cached and valid
        """
        if self.skip_cache:
            return False
        
        cache_file = self.cache_dir / cache_key
        return cache_file.exists()
    
    def mark_stage_cached(self, cache_key: str) -> None:
        """Mark stage as cached
        
        Args:
            cache_key: Unique key for the stage
        """
        cache_file = self.cache_dir / cache_key
        cache_file.write_text(json.dumps({
            "cached_at": datetime.now().isoformat(),
            "cache_key": cache_key
        }))
    
    def wait_for_barrier(self, barrier: str, timeout: int = 300) -> None:
        """Wait for barrier condition to be met
        
        Args:
            barrier: Barrier type (local, cluster_installed, cluster_accessible, cni_ready)
            timeout: Maximum wait time in seconds
            
        Raises:
            TimeoutError: If barrier not met within timeout
        """
        if barrier == "local":
            # No wait needed for local barrier
            return
        
        start_time = time.time()
        
        if barrier == "cluster_installed":
            # Wait for kubeconfig to exist
            kubeconfig = Path.home() / ".kube" / "config"
            while not kubeconfig.exists():
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Barrier '{barrier}' not met within {timeout}s")
                time.sleep(5)
        
        elif barrier == "cluster_accessible":
            # Wait for kubectl to work
            while True:
                try:
                    result = subprocess.run(
                        ["kubectl", "cluster-info"],
                        capture_output=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        break
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass
                
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Barrier '{barrier}' not met within {timeout}s")
                time.sleep(5)
        
        elif barrier == "cni_ready":
            # Wait for CNI pods to be ready
            while True:
                try:
                    result = subprocess.run(
                        ["kubectl", "get", "pods", "-n", "kube-system", 
                         "-l", "k8s-app=cilium", "-o", "json"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        pods_data = json.loads(result.stdout)
                        if pods_data.get("items"):
                            # Check if at least one pod is ready
                            for pod in pods_data["items"]:
                                conditions = pod.get("status", {}).get("conditions", [])
                                for condition in conditions:
                                    if condition.get("type") == "Ready" and condition.get("status") == "True":
                                        return
                except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
                    pass
                
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Barrier '{barrier}' not met within {timeout}s")
                time.sleep(5)
    
    def execute_stage(
        self,
        stage_name: str,
        script_path: Path,
        context_data: Dict[str, Any],
        cache_key: Optional[str] = None,
        barrier: str = "local",
        retry_count: int = 3
    ) -> StageResult:
        """Execute single bootstrap stage with caching and retry
        
        Args:
            stage_name: Name of the stage
            script_path: Path to script to execute
            context_data: Context data for the script
            cache_key: Cache key for the stage (None = no caching)
            barrier: Barrier to wait for before execution
            retry_count: Number of retries on failure
            
        Returns:
            StageResult with execution details
        """
        # Check cache
        if cache_key and self.is_stage_cached(cache_key):
            return StageResult(
                status="success",
                stage_name=stage_name,
                cached=True,
                duration_seconds=0,
                exit_code=0,
                stdout="",
                stderr=""
            )
        
        # Wait for barrier
        try:
            self.wait_for_barrier(barrier)
        except TimeoutError as e:
            return StageResult(
                status="failed",
                stage_name=stage_name,
                cached=False,
                duration_seconds=0,
                exit_code=1,
                stdout="",
                stderr="",
                error=str(e)
            )
        
        # Execute with retry
        last_error = None
        for attempt in range(retry_count):
            start_time = time.time()
            
            try:
                # Write context file
                context_file = Path(f"/tmp/ztc-context-{stage_name}.json")
                context_file.write_text(json.dumps(context_data))
                
                # Execute script
                result = subprocess.run(
                    [str(script_path)],
                    capture_output=True,
                    text=True,
                    env={**subprocess.os.environ, "ZTC_CONTEXT_FILE": str(context_file)},
                    timeout=600
                )
                
                duration = time.time() - start_time
                
                # Cleanup context file
                context_file.unlink(missing_ok=True)
                
                if result.returncode == 0:
                    # Success - mark cached
                    if cache_key:
                        self.mark_stage_cached(cache_key)
                    
                    return StageResult(
                        status="success",
                        stage_name=stage_name,
                        cached=False,
                        duration_seconds=duration,
                        exit_code=0,
                        stdout=result.stdout,
                        stderr=result.stderr
                    )
                else:
                    last_error = f"Exit code {result.returncode}: {result.stderr}"
                    
                    # Retry with exponential backoff
                    if attempt < retry_count - 1:
                        time.sleep(2 ** attempt)
            
            except subprocess.TimeoutExpired:
                last_error = "Script execution timed out"
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)
            
            except Exception as e:
                last_error = str(e)
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)
        
        # All retries failed
        return StageResult(
            status="failed",
            stage_name=stage_name,
            cached=False,
            duration_seconds=time.time() - start_time,
            exit_code=1,
            stdout="",
            stderr="",
            error=last_error
        )
