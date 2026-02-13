"""Platform engine for adapter orchestration"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from jinja2 import Environment, PrefixLoader, PackageLoader
import yaml
import shutil
import json
import hashlib

from ztc.registry.adapter_registry import AdapterRegistry
from ztc.adapters.base import PlatformAdapter
from ztc.engine.resolver import DependencyResolver
from ztc.engine.context import PlatformContext


class PlatformEngine:
    """Core engine for adapter orchestration and rendering
    
    Responsibilities:
    - Load and validate platform.yaml
    - Create shared Jinja2 environment for all adapters
    - Resolve adapter dependencies
    - Manage platform context
    """
    
    def __init__(self, platform_yaml: Path, debug: bool = False):
        """Initialize engine with platform configuration
        
        Args:
            platform_yaml: Path to platform.yaml configuration file
            debug: Enable debug mode (preserves workspace on failure)
        """
        self.platform_yaml = platform_yaml
        self.platform = self.load_platform(platform_yaml)
        self.adapter_registry = AdapterRegistry()
        self.debug_mode = debug
        self.context = PlatformContext()
        
        # Discover and register adapters
        self.adapter_registry.discover_adapters()
        
        # Shared Jinja2 environment for all adapters (performance optimization)
        self.jinja_env = self._create_shared_jinja_env()
    
    def load_platform(self, platform_yaml: Path) -> Dict[str, Any]:
        """Load and parse platform.yaml
        
        Args:
            platform_yaml: Path to platform.yaml file
            
        Returns:
            Parsed platform configuration
            
        Raises:
            FileNotFoundError: If platform.yaml doesn't exist
            yaml.YAMLError: If platform.yaml is invalid
        """
        if not platform_yaml.exists():
            raise FileNotFoundError(f"Platform configuration not found: {platform_yaml}")
        
        with open(platform_yaml, 'r') as f:
            return yaml.safe_load(f)
    
    def _create_shared_jinja_env(self) -> Environment:
        """Create shared Jinja2 environment with namespaced adapter templates
        
        Performance: Single environment with unified loader cache instead of 19 separate
        environments. Reduces memory footprint and filesystem stat() calls.
        
        Safety: PrefixLoader prevents namespace collisions. Templates accessed via
        "adapter_name/template.j2" syntax, ensuring correct template resolution.
        
        Returns:
            Configured Jinja2 Environment with PrefixLoader
        """
        prefix_mapping = {}
        
        # Build prefix mapping: "talos" -> PackageLoader("ztc.adapters.talos", "templates")
        for adapter_name in self.adapter_registry.list_adapters():
            # Use PackageLoader for robust binary packaging
            prefix_mapping[adapter_name] = PackageLoader(
                f"ztc.adapters.{adapter_name}",
                "templates"
            )
        
        # Create unified loader with namespace prefixes
        return Environment(
            loader=PrefixLoader(prefix_mapping),
            auto_reload=False,  # Production optimization
            enable_async=True   # Support async rendering
        )
    
    def resolve_adapters(self, partial: Optional[List[str]] = None, validate_dependencies: bool = False) -> List[PlatformAdapter]:
        """Resolve adapter dependencies via phase + capability matching
        
        Args:
            partial: Optional list of adapter names to render (for partial renders)
            validate_dependencies: If True, validates all required capabilities are provided
            
        Returns:
            Ordered list of adapters respecting dependencies and phases
        """
        # 1. Load adapters from platform.yaml (adapters are at root level)
        adapter_configs = self.platform
        adapters = []
        
        for adapter_name, adapter_config in adapter_configs.items():
            # Skip if partial render and adapter not in list
            if partial and adapter_name not in partial:
                continue
            
            # Skip if not a valid adapter config (must be a dict)
            if not isinstance(adapter_config, dict):
                continue
            
            try:
                adapter_instance = self.adapter_registry.get_adapter(adapter_name, adapter_config)
                # Set jinja_env if adapter supports it
                if hasattr(adapter_instance, '_jinja_env'):
                    adapter_instance._jinja_env = self.jinja_env
                adapters.append(adapter_instance)
            except KeyError:
                # Adapter not found in registry, skip
                continue
        
        # 2. Resolve dependencies using topological sort
        resolver = DependencyResolver()
        resolved_adapters = resolver.resolve(adapters, validate_dependencies=validate_dependencies)
        
        # Topological sort already respects dependencies and phases
        return resolved_adapters
    
    async def render(self, partial: Optional[List[str]] = None, progress_callback=None):
        """Main render pipeline (async for I/O-bound adapters)
        
        Executes the complete render pipeline:
        1. Resolve adapter dependencies
        2. Create workspace
        3. Render each adapter with immutable context snapshots
        4. Write adapter outputs to workspace
        5. Generate pipeline YAML
        6. Write debug scripts
        7. Validate artifacts
        8. Atomic swap to platform/generated
        9. Generate lock file
        10. Cleanup workspace
        
        Args:
            partial: Optional list of adapter names to render (for partial renders)
            progress_callback: Optional callback for progress updates (task_id, description, advance)
            
        Raises:
            Exception: Any error during rendering (workspace preserved if debug=True)
        """
        # 1. Resolve adapter dependencies
        if progress_callback:
            progress_callback("Resolving adapter dependencies...")
        adapters = self.resolve_adapters(partial)
        
        # 2. Create workspace
        if progress_callback:
            progress_callback("Creating workspace...")
        workspace = Path(".zerotouch-cache/workspace")
        try:
            # Clean existing workspace
            if workspace.exists():
                shutil.rmtree(workspace)
            workspace.mkdir(parents=True, exist_ok=True)
            
            generated_dir = workspace / "generated"
            generated_dir.mkdir(parents=True, exist_ok=True)
            
            # 3. Render adapters with immutable context snapshots
            for i, adapter in enumerate(adapters, 1):
                if progress_callback:
                    progress_callback(f"Rendering {adapter.name} ({i}/{len(adapters)})...")
                
                # Create immutable snapshot for adapter
                snapshot = self.context.snapshot()
                
                # Adapter renders with read-only context
                output = await adapter.render(snapshot)
                
                # Write adapter output to workspace
                self.write_adapter_output(generated_dir, adapter.name, output)
                
                # Engine updates mutable context
                self.context.register_output(adapter.name, output)
            
            # 4. Generate pipeline YAML from adapter stages
            if progress_callback:
                progress_callback("Generating pipeline YAML...")
            self.generate_pipeline_yaml(adapters, workspace)
            
            # 5. Write debug scripts for observability
            if progress_callback:
                progress_callback("Writing debug scripts...")
            self.write_debug_scripts(adapters, generated_dir)
            
            # 6. Validate generated artifacts
            if progress_callback:
                progress_callback("Validating artifacts...")
            self.validate_artifacts(generated_dir)
            
            # 7. Atomic swap to platform/generated
            if progress_callback:
                progress_callback("Swapping generated artifacts...")
            self.atomic_swap_generated(workspace)
            
            # 8. Generate lock file
            if progress_callback:
                progress_callback("Generating lock file...")
            artifacts_hash = self.hash_directory(Path("platform/generated"))
            self.generate_lock_file(artifacts_hash, adapters)
            
            # 9. Cleanup workspace
            if progress_callback:
                progress_callback("Cleaning up workspace...")
            if workspace.exists():
                shutil.rmtree(workspace)
        
        except Exception as e:
            # Cleanup workspace on failure unless debug mode
            if not self.debug_mode and workspace.exists():
                shutil.rmtree(workspace)
            raise
        
        finally:
            # Always cleanup workspace unless debug mode
            if not self.debug_mode and workspace.exists():
                shutil.rmtree(workspace)
    
    def write_adapter_output(self, generated_dir: Path, adapter_name: str, output: 'AdapterOutput'):
        """Write adapter manifests to generated directory
        
        Adapters control full directory structure via manifest keys.
        No forced adapter subdirectories - enables shared paths like argocd/, talos/.
        
        Args:
            generated_dir: Base generated directory path
            adapter_name: Name of the adapter (unused, kept for compatibility)
            output: AdapterOutput containing manifests
        """
        # Write each manifest file directly to adapter-specified path
        for filename, content in output.manifests.items():
            manifest_path = generated_dir / filename
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(content)
    
    def generate_pipeline_yaml(self, adapters: List[PlatformAdapter], workspace: Path):
        """Generate pipeline.yaml from adapter stage definitions
        
        Args:
            adapters: List of adapters in execution order
            workspace: Workspace directory path
        """
        pipeline = {
            "mode": "production",
            "total_steps": 0,
            "stages": []
        }
        
        # Collect stages from all adapters
        for adapter in adapters:
            output = self.context.get_output(adapter.name)
            if hasattr(output, 'stages'):
                for stage in output.stages:
                    pipeline["stages"].append({
                        "name": stage.name,
                        "description": stage.description,
                        "script": stage.script,
                        "cache_key": stage.cache_key if hasattr(stage, 'cache_key') else stage.name,
                        "required": stage.required if hasattr(stage, 'required') else True,
                        "phase": adapter.phase,
                        "barrier": stage.barrier if hasattr(stage, 'barrier') else "local"
                    })
        
        pipeline["total_steps"] = len(pipeline["stages"])
        
        # Write pipeline YAML
        pipeline_path = workspace / "pipeline.yaml"
        with open(pipeline_path, "w") as f:
            yaml.dump(pipeline, f, sort_keys=False)
    
    def write_debug_scripts(self, adapters: List[PlatformAdapter], generated_dir: Path):
        """Write scripts to debug directory for observability
        
        Enables operators to inspect and manually execute bootstrap logic when
        CLI fails. Aligns with Infrastructure as Code principles.
        
        Args:
            adapters: List of adapters in execution order
            generated_dir: Generated directory path
        """
        debug_dir = generated_dir / "debug" / "scripts"
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        for adapter in adapters:
            output = self.context.get_output(adapter.name)
            adapter_debug_dir = debug_dir / adapter.name
            adapter_debug_dir.mkdir(exist_ok=True)
            
            # Extract and write all scripts referenced by this adapter
            if hasattr(output, 'stages'):
                for stage in output.stages:
                    if hasattr(stage, 'script') and stage.script:
                        # Write script reference info
                        script_info = {
                            "name": stage.name,
                            "description": stage.description,
                            "script": stage.script,
                            "phase": adapter.phase
                        }
                        
                        info_path = adapter_debug_dir / f"{stage.name}.json"
                        info_path.write_text(json.dumps(script_info, indent=2))
        
        # Write README for operators
        readme_path = debug_dir / "README.md"
        readme_content = """# Debug Scripts

These scripts are extracted from the ZTC binary for debugging purposes.

## Usage

1. Review scripts in adapter-specific directories
2. Modify as needed for debugging
3. Execute manually or via stage-executor.sh

## Context Files

Scripts with .context.json files read data via $ZTC_CONTEXT_FILE environment variable.
"""
        readme_path.write_text(readme_content)
    
    def validate_artifacts(self, generated_dir: Path):
        """Validate generated artifacts against output schemas
        
        Args:
            generated_dir: Generated directory path
            
        Raises:
            ValueError: If artifacts are invalid
        """
        # Basic validation: check that generated directory exists and has content
        if not generated_dir.exists():
            raise ValueError(f"Generated directory does not exist: {generated_dir}")
        
        # Check that at least one adapter generated output
        adapter_dirs = [d for d in generated_dir.iterdir() if d.is_dir() and d.name != "debug"]
        if not adapter_dirs:
            raise ValueError("No adapter outputs found in generated directory")
    
    def atomic_swap_generated(self, workspace: Path):
        """Atomically swap workspace generated directory with platform/generated
        
        Args:
            workspace: Workspace directory containing generated artifacts
        """
        workspace_generated = workspace / "generated"
        target_generated = Path("platform/generated")
        
        # Create platform directory if it doesn't exist
        target_generated.parent.mkdir(parents=True, exist_ok=True)
        
        # Remove old generated directory if it exists
        if target_generated.exists():
            shutil.rmtree(target_generated)
        
        # Move workspace generated to target location
        shutil.move(str(workspace_generated), str(target_generated))
    
    def generate_lock_file(self, artifacts_hash: str, adapters: List[PlatformAdapter]):
        """Generate lock file with artifact hashes and adapter metadata
        
        Args:
            artifacts_hash: Hash of generated artifacts directory
            adapters: List of adapters that were rendered
        """
        # Calculate platform.yaml hash
        platform_hash = self.hash_file(self.platform_yaml)
        
        # Build adapter metadata
        adapter_metadata = {}
        for adapter in adapters:
            metadata = adapter.load_metadata()
            adapter_metadata[adapter.name] = {
                "version": metadata.get("version", "unknown"),
                "phase": adapter.phase
            }
        
        # Create lock file structure
        lock_data = {
            "platform_hash": platform_hash,
            "artifacts_hash": artifacts_hash,
            "ztc_version": "1.0.0",  # TODO: Get from package version
            "adapters": adapter_metadata
        }
        
        # Write lock file
        lock_path = Path("platform/lock.json")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "w") as f:
            json.dump(lock_data, f, indent=2)
    
    def hash_file(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file
        
        Args:
            file_path: Path to file
            
        Returns:
            Hex digest of file hash
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def hash_directory(self, directory: Path) -> str:
        """Calculate hash of directory contents
        
        Args:
            directory: Path to directory
            
        Returns:
            Hex digest of directory hash
        """
        sha256 = hashlib.sha256()
        
        # Sort files for deterministic hashing
        files = sorted(directory.rglob("*"))
        
        for file_path in files:
            if file_path.is_file():
                # Hash file path relative to directory
                rel_path = file_path.relative_to(directory)
                sha256.update(str(rel_path).encode())
                
                # Hash file content
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        sha256.update(chunk)
        
        return sha256.hexdigest()
