"""Script executor for running adapter scripts"""

import subprocess
import tempfile
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from ztc.adapters.base import ScriptReference


@dataclass
class ExecutionResult:
    """Result from script execution"""
    exit_code: int
    stdout: str
    stderr: str
    script_path: str


class ScriptExecutor:
    """Execute adapter scripts with context files and environment variables"""
    
    def __init__(self, working_dir: Optional[Path] = None):
        """Initialize script executor
        
        Args:
            working_dir: Working directory for script execution (defaults to current dir)
        """
        self.working_dir = working_dir or Path.cwd()
    
    def execute(
        self,
        script_ref: ScriptReference,
        context_data: Optional[Dict[str, Any]] = None,
        secret_env_vars: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        """Execute script with context file and environment variables
        
        Args:
            script_ref: Script reference with package and resource
            context_data: Context data to pass via JSON file (overrides script_ref.context_data)
            secret_env_vars: Secret environment variables (overrides script_ref.secret_env_vars)
        
        Returns:
            ExecutionResult with exit code, stdout, stderr
        """
        import importlib.resources
        
        # Get script content
        files = importlib.resources.files(script_ref.package)
        script_file = files / script_ref.resource.value
        script_content = script_file.read_text()
        
        # Use provided context_data or fall back to script_ref
        final_context_data = context_data if context_data is not None else script_ref.context_data or {}
        final_secret_env_vars = secret_env_vars if secret_env_vars is not None else script_ref.secret_env_vars or {}
        
        # Create temporary directory for script and context
        with tempfile.TemporaryDirectory(prefix="ztc-script-") as temp_dir:
            temp_path = Path(temp_dir)
            
            # Write script to temp file
            script_path = temp_path / "script.sh"
            script_path.write_text(script_content)
            script_path.chmod(0o755)
            
            # Write context data to JSON file
            context_file = temp_path / "context.json"
            context_file.write_text(json.dumps(final_context_data, indent=2))
            
            # Prepare environment variables
            env = os.environ.copy()
            env["ZTC_CONTEXT_FILE"] = str(context_file)
            env.update(final_secret_env_vars)
            
            # Execute script
            try:
                result = subprocess.run(
                    [str(script_path)],
                    cwd=self.working_dir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=script_ref.timeout
                )
                
                return ExecutionResult(
                    exit_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    script_path=str(script_path)
                )
            
            except subprocess.TimeoutExpired:
                return ExecutionResult(
                    exit_code=124,  # Standard timeout exit code
                    stdout="",
                    stderr=f"Script execution timed out after {script_ref.timeout} seconds",
                    script_path=str(script_path)
                )
            except Exception as e:
                return ExecutionResult(
                    exit_code=1,
                    stdout="",
                    stderr=f"Script execution failed: {e}",
                    script_path=str(script_path)
                )
