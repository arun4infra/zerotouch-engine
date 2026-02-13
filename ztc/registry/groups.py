"""Selection group management for dynamic UI grouping"""

from dataclasses import dataclass
from typing import List


@dataclass
class SelectionGroup:
    """Data-driven selection group for exclusive adapter categories
    
    Enables dynamic UI generation from adapter registry metadata.
    Scales to 19+ adapters without modifying workflow code.
    """
    name: str                    # e.g., "cloud_provider"
    prompt: str                  # User-facing prompt text
    options: List[str]           # Available adapter choices
    default: str                 # Default selection
    help_text: str = ""          # Optional help text


def build_selection_groups(registry: 'AdapterRegistry') -> List[SelectionGroup]:
    """Dynamically build selection groups from adapter registry metadata
    
    Scales to 19+ adapters without modifying workflow code.
    Adapters declare their selection_group in adapter.yaml metadata.
    
    Args:
        registry: AdapterRegistry instance with loaded adapters
        
    Returns:
        List of SelectionGroup objects for UI rendering
        
    Example:
        >>> registry = AdapterRegistry()
        >>> groups = build_selection_groups(registry)
        >>> for group in groups:
        ...     print(f"{group.prompt}: {group.options}")
        Select cloud provider: ['hetzner', 'aws', 'gcp']
        Select network tool: ['cilium', 'calico']
        Select operating system: ['talos', 'flatcar']
    """
    groups = {}
    
    for adapter_name in registry.list_adapters():
        adapter = registry.get_adapter(adapter_name)
        meta = adapter.load_metadata()
        
        # Use explicit selection_group or fall back to phase
        group_name = meta.get("selection_group", meta["phase"])
        
        if group_name not in groups:
            groups[group_name] = {
                "name": group_name,
                "prompt": meta.get("group_prompt", f"Select {group_name}"),
                "options": [],
                "default": None,
                "help_text": meta.get("group_help", "")
            }
        
        groups[group_name]["options"].append(adapter_name)
        
        # Set default if adapter declares it
        if meta.get("is_default", False):
            groups[group_name]["default"] = adapter_name
    
    # Convert to SelectionGroup objects
    selection_groups = []
    for group_data in groups.values():
        # Ensure default is set (use first option if not declared)
        if not group_data["default"]:
            group_data["default"] = group_data["options"][0]
        
        selection_groups.append(SelectionGroup(**group_data))
    
    return selection_groups
