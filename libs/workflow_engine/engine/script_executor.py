"""Script executor for running adapter scripts"""

import subprocess
import tempfile
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime

if TYPE_CHECKING:
    from workflow_engine.adapters.base import ScriptReference


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
        self.working_dir = working_dir or Path.cwd()
        self.log_dir = Path(".zerotouch-cache/init-logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def execute(
        self,
        script_ref: 'ScriptReference',
        context_data: Optional[Dict[str, Any]] = None,
        secret_env_vars: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        """Execute script with context file and environment variables"""
        import importlib.resources
        
        # Get script content
        files = importlib.resources.files(script_ref.package)
        script_file = files / script_ref.resource.value
        
        final_context_data = context_data if context_data is not None else script_ref.context_data or {}
        final_secret_env_vars = secret_env_vars if secret_env_vars is not None else script_ref.secret_env_vars or {}
        
        with tempfile.TemporaryDirectory(prefix="ztc-script-") as temp_dir:
            temp_path = Path(temp_dir)
            
            # Copy script
            script_path = temp_path / Path(script_ref.resource.value).name
            script_path.write_text(script_file.read_text())
            script_path.chmod(0o755)
            
            # Write context
            context_file = temp_path / "context.json"
            context_file.write_text(json.dumps(final_context_data, indent=2))
            
            # Execute
            env = os.environ.copy()
            env["ZTC_CONTEXT_FILE"] = str(context_file)
            env.update(final_secret_env_vars)
            
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
                    exit_code=124,
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
            
            # Log execution
            self._log_execution(script_ref, execution_result, final_context_data, final_secret_env_vars)
            
            return execution_result
    
    def _log_execution(
        self,
        script_ref: 'ScriptReference',
        result: ExecutionResult,
        context_data: Dict[str, Any],
        secret_env_vars: Dict[str, str]
    ):
        """Log script execution details"""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        script_name = Path(script_ref.resource.value).stem
        adapter_name = script_ref.package.split('.')[-2]
        
        log_filename = f"{timestamp}-{adapter_name}-{script_name}.log"
        log_path = self.log_dir / log_filename
        
        # Sanitize context
        sanitized_context = {
            k: "***REDACTED***" if any(s in k.lower() for s in ['key', 'secret', 'password', 'token']) else v 
            for k, v in context_data.items()
        }
        
        log_content = f"""=== Script Execution Log ===
Timestamp: {datetime.now().isoformat()}
Adapter: {adapter_name}
Script: {script_ref.resource.value}
Exit Code: {result.exit_code}

=== Context Data ===
{json.dumps(sanitized_context, indent=2)}

=== Environment Variables (Keys Only) ===
{json.dumps(list(secret_env_vars.keys()), indent=2)}

=== STDOUT ===
{result.stdout}

=== STDERR ===
{result.stderr}
"""
        log_path.write_text(log_content)
