"""Script executor for running adapter scripts"""

import subprocess
import tempfile
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
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
        self.log_dir = Path(".zerotouch-cache/init-logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
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
            
            # Copy entire scripts directory tree to preserve relative paths
            # files already points to the scripts package root
            if files.is_dir():
                self._copy_scripts_recursive(files, temp_path)
            
            # Main script path (relative to scripts root)
            script_rel_path = Path(script_ref.resource.value)
            script_path = temp_path / script_rel_path
            
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
                
                execution_result = ExecutionResult(
                    exit_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    script_path=str(script_path)
                )
            
            except subprocess.TimeoutExpired:
                execution_result = ExecutionResult(
                    exit_code=124,  # Standard timeout exit code
                    stdout="",
                    stderr=f"Script execution timed out after {script_ref.timeout} seconds",
                    script_path=str(script_path)
                )
            except Exception as e:
                execution_result = ExecutionResult(
                    exit_code=1,
                    stdout="",
                    stderr=f"Script execution failed: {e}",
                    script_path=str(script_path)
                )
            
            # Log execution details before temp cleanup
            self._log_execution(script_ref, execution_result, final_context_data, final_secret_env_vars)
            
            return execution_result

    def _log_execution(
        self,
        script_ref: ScriptReference,
        result: ExecutionResult,
        context_data: Dict[str, Any],
        secret_env_vars: Dict[str, str]
    ):
        """Log script execution details to persistent storage
        
        Args:
            script_ref: Script reference
            result: Execution result
            context_data: Context data (will be sanitized)
            secret_env_vars: Secret environment variables (only keys logged)
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        script_name = Path(script_ref.resource.value).stem
        adapter_name = script_ref.package.split('.')[-2]  # Extract adapter name from package
        
        log_filename = f"{timestamp}-{adapter_name}-{script_name}.log"
        log_path = self.log_dir / log_filename
        
        # Sanitize context data (remove sensitive values)
        sanitized_context = {k: "***REDACTED***" if any(s in k.lower() for s in ['key', 'secret', 'password', 'token']) else v 
                            for k, v in context_data.items()}
        
        log_content = f"""
=== Script Execution Log ===
Timestamp: {datetime.now().isoformat()}
Adapter: {adapter_name}
Script: {script_ref.resource.value}
Exit Code: {result.exit_code}
Script Path: {result.script_path}

=== Context Data ===
{json.dumps(sanitized_context, indent=2)}

=== Environment Variables (Keys Only) ===
{json.dumps(list(secret_env_vars.keys()), indent=2)}

=== STDOUT ===
{result.stdout}

=== STDERR ===
{result.stderr}

=== End of Log ===
"""
        
        try:
            log_path.write_text(log_content)
        except Exception as e:
            # Don't fail execution if logging fails
            print(f"Warning: Failed to write execution log: {e}")

    def _copy_scripts_recursive(self, source_dir, dest_dir: Path):
        """Recursively copy all .sh files preserving directory structure
        
        Args:
            source_dir: Source directory (importlib.resources traversable)
            dest_dir: Destination directory path
        """
        for item in source_dir.iterdir():
            if item.is_file() and item.name.endswith('.sh'):
                dest_file = dest_dir / item.name
                dest_file.write_text(item.read_text())
                dest_file.chmod(0o755)
            elif item.is_dir():
                # Create subdirectory and recurse
                sub_dest = dest_dir / item.name
                sub_dest.mkdir(exist_ok=True)
                self._copy_scripts_recursive(item, sub_dest)
