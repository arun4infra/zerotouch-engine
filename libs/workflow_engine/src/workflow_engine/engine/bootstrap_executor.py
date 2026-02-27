"""Bootstrap executor - reads pipeline.yaml and executes stages"""

import yaml
import subprocess
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from workflow_engine.services.age_key_provider import AgeKeyProvider


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
        
        # Setup logging
        self.log_dir = Path(".zerotouch-cache/logs/bootstrap")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Load pipeline
        with open(pipeline_path) as f:
            self.pipeline = yaml.safe_load(f)
        
        # Initialize cache
        if not self.cache_file.exists():
            self.cache_file.write_text('{"stages":{}}')
        
        # Use singleton secrets provider (prevents multiple S3 calls)
        from workflow_engine.services.secrets_provider import SecretsProvider
        self._secrets_provider = SecretsProvider()
    
    def _decrypt_secrets(self) -> Dict[str, Dict[str, str]]:
        """Decrypt all secrets from platform/generated/secrets/
        
        Uses hybrid approach:
        - Local dev: Age key from ~/.config/sops/age/keys.txt
        - CI/CD: SOPS_AGE_KEY environment variable
        
        Returns:
            dict: {secret_name: {key: value}} - kept in memory only
        """
        secrets = {}
        secrets_dir = Path('platform/generated/secrets')
        
        if not secrets_dir.exists():
            print(f"ℹ️  Secrets directory not found: {secrets_dir}")
            print("   Secrets will not be available for this operation")
            return secrets
        
        # Check for Age key (hybrid model)
        age_key_provider = AgeKeyProvider(Path('platform/platform.yaml'))
        age_key = age_key_provider.get_age_key()
        
        if not age_key:
            print("⚠️  Age private key not found. Secrets will not be available.")
            print("   Local dev: Place key in ~/.ztp_cli/secrets")
            print("   CI/CD: Set SOPS_AGE_KEY environment variable")
            print("   S3: Ensure S3 credentials and config in platform.yaml")
            return secrets
        
        # Decrypt each secret file
        secret_files = list(secrets_dir.glob('*.secret.yaml'))
        if not secret_files:
            print(f"ℹ️  No secret files found in {secrets_dir}")
            return secrets
        
        print(f"🔓 Decrypting {len(secret_files)} secret(s)...")
        for secret_file in secret_files:
            try:
                # Set Age key in environment for SOPS
                env = os.environ.copy()
                env['SOPS_AGE_KEY'] = age_key
                
                result = subprocess.run(
                    ['sops', '-d', str(secret_file)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=env
                )
                
                if result.returncode == 0:
                    secret_data = yaml.safe_load(result.stdout)
                    secret_name = secret_data['metadata']['name']
                    # Extract stringData (decrypted values)
                    secrets[secret_name] = secret_data.get('stringData', {})
                    print(f"   ✓ Decrypted: {secret_name}")
                else:
                    print(f"   ✗ Failed to decrypt {secret_file.name}: {result.stderr}")
            except subprocess.TimeoutExpired:
                print(f"   ✗ Timeout decrypting {secret_file.name}")
            except Exception as e:
                print(f"   ✗ Error decrypting {secret_file.name}: {e}")
        
        if secrets:
            print(f"✓ Successfully decrypted {len(secrets)} secret(s)")
        
        return secrets
    
    def __del__(self):
        """Cleanup on deletion"""
        # Secrets are managed by singleton provider
        pass
    
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
        script_path = Path('libs/workflow_engine/src/workflow_engine/adapters') / script
        
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
        
        # Prepare environment (export platform.yaml data as env vars)
        env = self._prepare_environment(stage)
        
        # Setup logging
        log_file = self.log_dir / f"{stage_name}.log"
        
        # Execute script
        try:
            # Build args and expand environment variables (legacy pattern)
            args = stage.get('args', [])
            expanded_args = []
            for arg in args:
                import os
                expanded_arg = os.path.expandvars(str(arg))
                expanded_args.append(expanded_arg)
            
            # Log execution start
            with open(log_file, 'w') as f:
                f.write(f"=== Stage: {stage_name} ===\n")
                f.write(f"Script: {script_path}\n")
                f.write(f"Args: {expanded_args}\n")
                f.write(f"Time: {datetime.now().isoformat()}\n\n")
            
            # Run script with real-time output streaming using threading
            import threading
            
            def stream_output(pipe, output_list, log_file):
                """Stream output from pipe to console and log file"""
                for line in iter(pipe.readline, ''):
                    if line:
                        print(line, end='', flush=True)
                        output_list.append(line)
                        with open(log_file, 'a') as f:
                            f.write(line)
            
            process = subprocess.Popen(
                ['bash', str(script_path)] + expanded_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=1,  # Line buffered
                env=env
            )
            
            stdout_lines = []
            
            # Start thread to stream output
            thread = threading.Thread(
                target=stream_output,
                args=(process.stdout, stdout_lines, log_file)
            )
            thread.start()
            
            # Wait for process to complete
            returncode = process.wait(timeout=stage.get('timeout', 600))
            thread.join()
            
            stdout = ''.join(stdout_lines)
            stderr = ''
            
            # Log summary
            with open(log_file, 'a') as f:
                f.write(f"\n\n=== Exit Code: {returncode} ===\n")
            
            if returncode == 0:
                # Mark as cached
                if cache_key and cache_key != 'null':
                    self._mark_cached(cache_key)
                
                return StageResult(
                    success=True,
                    stage_name=stage_name,
                    output=stdout,
                    error=None,
                    cached=False,
                    exit_code=returncode
                )
            else:
                return StageResult(
                    success=False,
                    stage_name=stage_name,
                    output=stdout,
                    error=stderr,
                    cached=False,
                    exit_code=returncode
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
        """Prepare environment variables and context file
        
        Uses ContextProvider to delegate context building to adapters.
        Injects secrets as environment variables (never written to disk).
        """
        import os
        env = os.environ.copy()
        
        # Get adapter name
        adapter_name = stage.get('adapter')
        if not adapter_name:
            return env
        
        # Use ContextProvider to build and write context (adapter-owned logic)
        from workflow_engine.services.context_provider import ContextProvider
        context_provider = ContextProvider()
        
        try:
            context_file = context_provider.write_stage_context(stage['name'], adapter_name)
            env['ZTC_CONTEXT_FILE'] = str(context_file.absolute())
        except Exception as e:
            raise ValueError(f"Stage '{stage['name']}' context creation failed: {e}")
        
        # Add common environment variables
        common_env = context_provider.get_common_env_vars()
        env.update(common_env)
        
        # Add project root for scripts
        env['PROJECT_ROOT'] = str(Path.cwd())
        
        # Read rescue password from cache for SSH access
        rescue_password_file = Path('.zerotouch-cache/rescue-password.txt')
        if rescue_password_file.exists():
            env['SSH_PASSWORD'] = rescue_password_file.read_text().strip()
        
        # Inject secrets as environment variables (delegated to provider)
        secret_env = self._secrets_provider.get_env_vars()
        env.update(secret_env)
        
        return env
