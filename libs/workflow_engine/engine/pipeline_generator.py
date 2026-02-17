"""Pipeline YAML generation and artifact validation"""

import yaml
import json
from pathlib import Path
from typing import List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from workflow_engine.adapters.base import PlatformAdapter


class PipelineGenerator:
    """Generate pipeline.yaml and debug scripts from adapters"""
    
    def generate_pipeline_yaml(
        self,
        adapters: List['PlatformAdapter'],
        adapter_outputs: Dict[str, Any],
        output_path: Path
    ) -> Dict[str, Any]:
        """Generate pipeline.yaml from adapter stage definitions
        
        Args:
            adapters: List of adapters in execution order
            adapter_outputs: Map of adapter_name → AdapterOutput
            output_path: Path to write pipeline.yaml
            
        Returns:
            Pipeline data structure
        """
        pipeline = {
            "mode": "production",
            "total_steps": 0,
            "stages": []
        }
        
        # Collect stages from all adapters
        for adapter in adapters:
            if adapter.name not in adapter_outputs:
                continue
            
            output = adapter_outputs[adapter.name]
            if hasattr(output, 'stages') and output.stages:
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
        
        # Write pipeline YAML
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            yaml.dump(pipeline, f, sort_keys=False)
        
        return pipeline
    
    def write_debug_scripts(
        self,
        adapters: List['PlatformAdapter'],
        adapter_outputs: Dict[str, Any],
        output_dir: Path
    ) -> int:
        """Write scripts to debug directory for observability
        
        Args:
            adapters: List of adapters in execution order
            adapter_outputs: Map of adapter_name → AdapterOutput
            output_dir: Debug directory path
            
        Returns:
            Number of scripts written
        """
        debug_dir = output_dir / "debug" / "scripts"
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        script_count = 0
        
        for adapter in adapters:
            if adapter.name not in adapter_outputs:
                continue
            
            output = adapter_outputs[adapter.name]
            adapter_debug_dir = debug_dir / adapter.name
            adapter_debug_dir.mkdir(exist_ok=True)
            
            # Extract and write all scripts referenced by this adapter
            if hasattr(output, 'stages') and output.stages:
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
                        script_count += 1
        
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
        
        return script_count
    
    def validate_artifacts(self, generated_dir: Path) -> Dict[str, Any]:
        """Validate generated artifacts
        
        Args:
            generated_dir: Generated directory path
            
        Returns:
            Validation result with errors if any
        """
        errors = []
        
        # Check that generated directory exists
        if not generated_dir.exists():
            errors.append({
                "type": "missing_directory",
                "message": f"Generated directory does not exist: {generated_dir}"
            })
            return {"valid": False, "errors": errors}
        
        # Check that at least one adapter generated output
        adapter_dirs = [
            d for d in generated_dir.iterdir()
            if d.is_dir() and d.name not in ["debug", ".git"]
        ]
        
        if not adapter_dirs:
            errors.append({
                "type": "no_adapter_outputs",
                "message": "No adapter outputs found in generated directory"
            })
        
        # Check for pipeline.yaml
        pipeline_yaml = generated_dir / "pipeline.yaml"
        if not pipeline_yaml.exists():
            errors.append({
                "type": "missing_pipeline",
                "message": "pipeline.yaml not found in generated directory"
            })
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "adapter_count": len(adapter_dirs)
        }
