"""Bootstrap pipeline generator"""

import yaml
from pathlib import Path
from typing import Dict, Any


def generate_bootstrap_pipeline(platform_yaml_path: Path, output_path: Path) -> None:
    """Generate bootstrap pipeline.yaml from template and platform.yaml
    
    Args:
        platform_yaml_path: Path to platform.yaml
        output_path: Path to write pipeline.yaml
    """
    # Load platform.yaml
    with open(platform_yaml_path) as f:
        platform_data = yaml.safe_load(f)
    
    # Build selection_group -> adapter mapping
    adapter_map = _build_adapter_map(platform_data['adapters'])
    
    # Load template
    template_path = Path(__file__).parent.parent / "templates" / "bootstrap" / "production.yaml"
    with open(template_path) as f:
        pipeline_template = yaml.safe_load(f)
    
    # Replace placeholders
    pipeline = _replace_placeholders(pipeline_template, adapter_map)
    
    # Write pipeline.yaml
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        yaml.dump(pipeline, f, sort_keys=False, default_flow_style=False)


def _build_adapter_map(adapters: Dict[str, Any]) -> Dict[str, str]:
    """Build mapping from selection_group to adapter name
    
    Args:
        adapters: Dict of adapter configs from platform.yaml
        
    Returns:
        Dict mapping selection_group to adapter name
    """
    from workflow_engine.registry import AdapterRegistry
    
    registry = AdapterRegistry()
    adapter_map = {}
    
    for adapter_name in adapters.keys():
        metadata = registry.get_metadata(adapter_name)
        selection_group = metadata.get('selection_group')
        if selection_group:
            adapter_map[selection_group] = adapter_name
    
    return adapter_map


def _replace_placeholders(pipeline: Dict[str, Any], adapter_map: Dict[str, str]) -> Dict[str, Any]:
    """Replace {selection_group} placeholders with actual adapter names
    
    Args:
        pipeline: Pipeline template dict
        adapter_map: Mapping from selection_group to adapter name
        
    Returns:
        Pipeline with placeholders replaced
    """
    for stage in pipeline['stages']:
        selection_group = stage.get('selection_group')
        if not selection_group:
            continue
        
        # Get actual adapter name
        adapter_name = adapter_map.get(selection_group)
        if not adapter_name:
            # Skip stages for adapters not in platform.yaml
            stage['skip'] = True
            continue
        
        # Replace placeholder in adapter field
        stage['adapter'] = adapter_name
        
        # Replace placeholder in script path
        script = stage.get('script', '')
        if script:
            # Replace {selection_group} with adapter name
            stage['script'] = f"{adapter_name}/scripts/{script}"
    
    # Remove skipped stages
    pipeline['stages'] = [s for s in pipeline['stages'] if not s.get('skip')]
    pipeline['total_steps'] = len(pipeline['stages'])
    
    return pipeline
