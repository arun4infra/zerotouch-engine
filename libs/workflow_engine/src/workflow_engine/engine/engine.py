"""Platform engine for adapter orchestration"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from jinja2 import Environment, PrefixLoader, PackageLoader
import yaml
import shutil
import json
import hashlib

from workflow_engine.registry.adapter_registry import AdapterRegistry
from workflow_engine.adapters.base import PlatformAdapter
from workflow_engine.engine.resolver import DependencyResolver
from workflow_engine.engine.context import PlatformContext


class PlatformEngine:
    """Core engine for adapter orchestration and rendering"""
    
    def __init__(self, platform_yaml: Path, debug: bool = False):
        self.platform_yaml = platform_yaml
        self.platform = self.load_platform(platform_yaml)
        self.secrets = self.load_secrets()
        self.versions = self.load_versions()
        self.adapter_registry = AdapterRegistry()
        self.debug_mode = debug
        self.context = PlatformContext()
        self.adapter_registry.discover_adapters()
        self.jinja_env = self._create_shared_jinja_env()
    
    def load_platform(self, platform_yaml: Path) -> Dict[str, Any]:
        if not platform_yaml.exists():
            raise FileNotFoundError(f"Platform configuration not found: {platform_yaml}")
        with open(platform_yaml, 'r') as f:
            return yaml.safe_load(f)
    
    def load_secrets(self) -> Dict[str, Dict[str, str]]:
        secrets_file = Path.home() / ".ztp" / "secrets"
        if not secrets_file.exists():
            return {}
        try:
            import configparser
            import base64
            config = configparser.ConfigParser()
            config.read(secrets_file)
            secrets = {}
            for section in config.sections():
                secrets[section] = {}
                for key, value in config.items(section):
                    if value.startswith("base64:"):
                        decoded = base64.b64decode(value[7:]).decode()
                        secrets[section][key] = decoded
                    else:
                        secrets[section][key] = value
            return secrets
        except Exception:
            return {}
    
    def load_versions(self) -> Dict[str, Any]:
        """Load versions.yaml based on platform version"""
        platform_version = self.platform.get('version', '1.0')
        # Normalize version: '1.0' -> '1.0', '1.0.0' -> '1.0'
        version_dir = platform_version.rsplit('.', 1)[0] if platform_version.count('.') > 1 else platform_version
        
        versions_path = Path(__file__).parent.parent / "versions" / version_dir / "versions.yaml"
        if not versions_path.exists():
            # Fallback to 1.0 if version not found
            versions_path = Path(__file__).parent.parent / "versions" / "1.0" / "versions.yaml"
        
        if versions_path.exists():
            with open(versions_path, 'r') as f:
                return yaml.safe_load(f)
        return {"adapters": {}}
    
    def _create_shared_jinja_env(self) -> Environment:
        prefix_mapping = {}
        for adapter_name in self.adapter_registry.list_adapters():
            prefix_mapping[adapter_name] = PackageLoader(
                f"workflow_engine.adapters.{adapter_name}",
                "templates"
            )
        return Environment(
            loader=PrefixLoader(prefix_mapping),
            auto_reload=False,
            enable_async=True
        )
    
    def resolve_adapters(self, partial: Optional[List[str]] = None, validate_dependencies: bool = False) -> List[PlatformAdapter]:
        adapter_configs = self.platform.get('adapters', {})
        adapters = []
        
        # First, load explicitly configured adapters
        for adapter_name, adapter_config in adapter_configs.items():
            if partial and adapter_name not in partial:
                continue
            if not isinstance(adapter_config, dict):
                continue
            merged_config = adapter_config.copy()
            if adapter_name in self.secrets:
                merged_config.update(self.secrets[adapter_name])
            try:
                adapter_instance = self.adapter_registry.get_adapter(adapter_name, merged_config)
                if hasattr(adapter_instance, '_jinja_env'):
                    adapter_instance._jinja_env = self.jinja_env
                adapters.append(adapter_instance)
            except KeyError:
                continue
        
        # Build capability map from configured adapters
        provided_capabilities = set()
        for adapter in adapters:
            metadata = adapter.load_metadata()
            provides = metadata.get("provides", [])
            for capability in provides:
                cap_name = capability["capability"] if isinstance(capability, dict) else capability
                provided_capabilities.add(cap_name)
        
        # Auto-include adapters whose dependencies are satisfied
        configured_names = set(adapter_configs.keys())
        for adapter_name in self.adapter_registry.list_adapters():
            if adapter_name in configured_names:
                continue  # Already added
            if partial and adapter_name not in partial:
                continue
            
            try:
                metadata = self.adapter_registry.get_metadata(adapter_name)
                requires = metadata.get("requires", [])
                
                # Check if all required capabilities are provided
                all_satisfied = True
                for requirement in requires:
                    req_cap = requirement["capability"] if isinstance(requirement, dict) else requirement
                    if req_cap not in provided_capabilities:
                        all_satisfied = False
                        break
                
                if all_satisfied:
                    # Build default config from versions.yaml
                    adapter_defaults = self.versions.get("adapters", {}).get(adapter_name, {})
                    default_config = {}
                    
                    # Map default_ prefixed keys to actual config keys
                    for key, value in adapter_defaults.items():
                        if key.startswith("default_"):
                            config_key = key.replace("default_", "")
                            default_config[config_key] = value
                    
                    # Inherit mode from argocd if not in defaults
                    if "mode" not in default_config:
                        argocd_config = adapter_configs.get("argocd", {})
                        default_config["mode"] = argocd_config.get("mode", "production")
                    
                    # Infer provider for external_dns from cloud provider
                    if adapter_name == "external_dns" and "provider" in default_config:
                        if "hetzner" in configured_names:
                            default_config["provider"] = "hetzner"
                        elif "aws" in configured_names:
                            default_config["provider"] = "aws"
                    
                    adapter_instance = self.adapter_registry.get_adapter(adapter_name, default_config)
                    if hasattr(adapter_instance, '_jinja_env'):
                        adapter_instance._jinja_env = self.jinja_env
                    adapters.append(adapter_instance)
            except (KeyError, Exception):
                continue
        
        resolver = DependencyResolver()
        return resolver.resolve(adapters, validate_dependencies=validate_dependencies)
    
    async def render(self, partial: Optional[List[str]] = None, progress_callback=None):
        from datetime import datetime
        log_dir = Path(".zerotouch-cache/render-logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_file = log_dir / f"{timestamp}-render.log"
        
        def log(message: str):
            try:
                with open(log_file, "a") as f:
                    f.write(f"[{datetime.now().isoformat()}] {message}\n")
            except Exception:
                pass
        
        log("=== Render Started ===")
        if progress_callback:
            progress_callback("Resolving adapter dependencies...")
        adapters = self.resolve_adapters(partial)
        
        workspace = Path(".zerotouch-cache/workspace")
        try:
            if workspace.exists():
                shutil.rmtree(workspace)
            workspace.mkdir(parents=True, exist_ok=True)
            generated_dir = workspace / "generated"
            generated_dir.mkdir(parents=True, exist_ok=True)
            
            for i, adapter in enumerate(adapters, 1):
                if progress_callback:
                    progress_callback(f"Rendering {adapter.name} ({i}/{len(adapters)})...")
                snapshot = self.context.snapshot()
                output = await adapter.render(snapshot)
                self.write_adapter_output(generated_dir, adapter.name, output)
                self.context.register_output(adapter.name, output)
            
            if progress_callback:
                progress_callback("Generating pipeline YAML...")
            self.generate_pipeline_yaml(adapters, workspace)
            
            if progress_callback:
                progress_callback("Validating artifacts...")
            self.validate_artifacts(generated_dir)
            
            if progress_callback:
                progress_callback("Generating kustomization files...")
            self.generate_kustomization_files(generated_dir)
            
            if progress_callback:
                progress_callback("Swapping generated artifacts...")
            self.atomic_swap_generated(workspace)
            
            if progress_callback:
                progress_callback("Generating lock file...")
            artifacts_hash = self.hash_directory(Path("platform/generated"))
            self.generate_lock_file(artifacts_hash, adapters)
            
            if workspace.exists():
                shutil.rmtree(workspace)
            log("=== Render Completed Successfully ===")
        except Exception as e:
            log(f"=== Render Failed: {str(e)} ===")
            if not self.debug_mode and workspace.exists():
                shutil.rmtree(workspace)
            raise
    
    def write_adapter_output(self, generated_dir: Path, adapter_name: str, output):
        for filename, content in output.manifests.items():
            manifest_path = generated_dir / filename
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(content)
    
    def generate_pipeline_yaml(self, adapters: List[PlatformAdapter], workspace: Path):
        pipeline = {"mode": "production", "total_steps": 0, "stages": []}
        for adapter in adapters:
            output = self.context.get_output(adapter.name)
            if hasattr(output, 'stages'):
                for stage in output.stages:
                    pipeline["stages"].append({
                        "name": stage.name,
                        "description": stage.description,
                        "script": stage.script,
                        "cache_key": getattr(stage, 'cache_key', stage.name),
                        "required": getattr(stage, 'required', True),
                        "phase": adapter.phase,
                        "barrier": getattr(stage, 'barrier', "local")
                    })
        pipeline["total_steps"] = len(pipeline["stages"])
        with open(workspace / "pipeline.yaml", "w") as f:
            yaml.dump(pipeline, f, sort_keys=False)
    
    def generate_kustomization_files(self, generated_dir: Path):
        """Generate kustomization.yaml files for base, core, and foundation"""
        
        # 1. Generate argocd/base/kustomization.yaml
        base_dir = generated_dir / "argocd" / "base"
        if base_dir.exists():
            base_files = sorted([f.name for f in base_dir.iterdir() if f.is_file() and f.suffix == '.yaml'])
            if base_files:
                kustomization_content = "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\n\nresources:\n"
                for file in base_files:
                    kustomization_content += f"- {file}\n"
                (base_dir / "kustomization.yaml").write_text(kustomization_content)
        
        # 2. Generate argocd/k8/core/kustomization.yaml
        core_dir = generated_dir / "argocd" / "k8" / "core"
        if core_dir.exists():
            # Get all yaml files (excluding subdirectories and .gitkeep)
            core_files = sorted([f.name for f in core_dir.iterdir() if f.is_file() and f.suffix == '.yaml'])
            
            kustomization_content = "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\n\nresources:\n"
            for file in core_files:
                kustomization_content += f"- {file}\n"
            
            # Add subdirectories that contain kustomization.yaml
            for subdir in sorted(core_dir.iterdir()):
                if subdir.is_dir() and (subdir / "kustomization.yaml").exists():
                    kustomization_content += f"- {subdir.name}\n"
            
            (core_dir / "kustomization.yaml").write_text(kustomization_content)
        
        # 3. Generate argocd/k8/foundation/kustomization.yaml
        foundation_dir = generated_dir / "argocd" / "k8" / "foundation"
        if foundation_dir.exists():
            foundation_files = sorted([f.name for f in foundation_dir.iterdir() if f.is_file() and f.suffix == '.yaml'])
            
            kustomization_content = "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\n\nresources:\n"
            for file in foundation_files:
                kustomization_content += f"- {file}\n"
            
            # Add subdirectories that contain kustomization.yaml
            for subdir in sorted(foundation_dir.iterdir()):
                if subdir.is_dir() and (subdir / "kustomization.yaml").exists():
                    kustomization_content += f"- {subdir.name}\n"
            
            (foundation_dir / "kustomization.yaml").write_text(kustomization_content)
        
        # 4. Generate argocd/kind/core/kustomization.yaml
        kind_core_dir = generated_dir / "argocd" / "kind" / "core"
        if kind_core_dir.exists():
            kind_files = sorted([f.name for f in kind_core_dir.iterdir() if f.is_file() and f.suffix == '.yaml'])
            
            if kind_files:
                kustomization_content = "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\n\nresources:\n"
                for file in kind_files:
                    kustomization_content += f"- {file}\n"
                
                (kind_core_dir / "kustomization.yaml").write_text(kustomization_content)
    
    def validate_artifacts(self, generated_dir: Path):
        if not generated_dir.exists():
            raise ValueError(f"Generated directory does not exist: {generated_dir}")
        adapter_dirs = [d for d in generated_dir.iterdir() if d.is_dir() and d.name != "debug"]
        if not adapter_dirs:
            raise ValueError("No adapter outputs found in generated directory")
    
    def atomic_swap_generated(self, workspace: Path):
        workspace_generated = workspace / "generated"
        target_generated = Path("platform/generated")
        target_generated.parent.mkdir(parents=True, exist_ok=True)
        if target_generated.exists():
            shutil.rmtree(target_generated)
        shutil.move(str(workspace_generated), str(target_generated))
    
    def generate_lock_file(self, artifacts_hash: str, adapters: List[PlatformAdapter]):
        platform_hash = self.hash_file(self.platform_yaml)
        adapter_metadata = {}
        for adapter in adapters:
            metadata = adapter.load_metadata()
            adapter_metadata[adapter.name] = {
                "version": metadata.get("version", "unknown"),
                "phase": adapter.phase
            }
        lock_data = {
            "platform_hash": platform_hash,
            "artifacts_hash": artifacts_hash,
            "ztc_version": "1.0.0",
            "adapters": adapter_metadata
        }
        with open(Path("platform/lock.json"), "w") as f:
            json.dump(lock_data, f, indent=2)
    
    def hash_file(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def hash_directory(self, directory: Path) -> str:
        sha256 = hashlib.sha256()
        for file_path in sorted(directory.rglob("*")):
            if file_path.is_file():
                sha256.update(str(file_path.relative_to(directory)).encode())
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        sha256.update(chunk)
        return sha256.hexdigest()
