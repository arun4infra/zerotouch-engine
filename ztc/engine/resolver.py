"""Dependency resolution with topological sort"""

from typing import List, Dict
from ztc.adapters.base import PlatformAdapter


class MissingCapabilityError(Exception):
    """Raised when required capability is not provided by any adapter"""
    pass


class CircularDependencyError(Exception):
    """Raised when circular dependency is detected"""
    pass


class DependencyResolver:
    """Resolves adapter dependencies using topological sort"""
    
    def resolve(self, adapters: List[PlatformAdapter]) -> List[PlatformAdapter]:
        """Topological sort with phase-based ordering
        
        Args:
            adapters: List of adapters to resolve
            
        Returns:
            Ordered list of adapters respecting dependencies
            
        Raises:
            MissingCapabilityError: If required capability not provided
            CircularDependencyError: If circular dependency detected
        """
        # Build capability registry
        capability_registry = {}
        for adapter in adapters:
            metadata = adapter.load_metadata()
            provides = metadata.get("provides", [])
            
            for capability in provides:
                cap_name = capability["capability"] if isinstance(capability, dict) else capability
                capability_registry[cap_name] = adapter
        
        # Build dependency graph
        graph = {}
        in_degree = {}
        
        for adapter in adapters:
            graph[adapter] = []
            in_degree[adapter] = 0
        
        for adapter in adapters:
            metadata = adapter.load_metadata()
            requires = metadata.get("requires", [])
            
            for requirement in requires:
                req_cap = requirement["capability"] if isinstance(requirement, dict) else requirement
                
                if req_cap not in capability_registry:
                    raise MissingCapabilityError(
                        f"Adapter '{adapter.name}' requires capability '{req_cap}' "
                        f"but no adapter provides it"
                    )
                
                provider = capability_registry[req_cap]
                graph[provider].append(adapter)
                in_degree[adapter] += 1
        
        # Kahn's algorithm for topological sort
        queue = [adapter for adapter in adapters if in_degree[adapter] == 0]
        result = []
        
        while queue:
            adapter = queue.pop(0)
            result.append(adapter)
            
            for dependent in graph[adapter]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        if len(result) != len(adapters):
            raise CircularDependencyError("Circular dependency detected in adapters")
        
        return result
