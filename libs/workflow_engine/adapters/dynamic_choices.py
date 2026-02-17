"""Dynamic choice resolution for adapter input prompts"""

from typing import List, Optional, Dict, Any
from .base import InputPrompt, PlatformAdapter


class DynamicChoiceResolver:
    """Resolves dynamic choices for adapter input prompts at runtime
    
    This class checks if an InputPrompt has a get_dynamic_choices method
    and calls it with the current PlatformContext to fetch choices at runtime.
    Results are cached to avoid redundant API calls.
    """
    
    def __init__(self):
        """Initialize resolver with empty cache"""
        self._cache: Dict[str, List[str]] = {}
    
    def _build_cache_key(
        self, 
        adapter: PlatformAdapter, 
        input_prompt: InputPrompt,
        context: Dict[str, Any]
    ) -> str:
        """Build cache key from adapter, prompt, and relevant context
        
        Args:
            adapter: PlatformAdapter instance
            input_prompt: InputPrompt to resolve choices for
            context: PlatformContext dictionary
            
        Returns:
            Cache key string
        """
        # Include adapter name, prompt name, and relevant context values
        # that might affect dynamic choices
        context_hash = hash(frozenset(context.items()))
        return f"{adapter.name}:{input_prompt.name}:{context_hash}"
    
    async def resolve_choices(
        self,
        adapter: PlatformAdapter,
        input_prompt: InputPrompt,
        context: Dict[str, Any]
    ) -> List[str]:
        """Resolve choices for input prompt, using cache when available
        
        Args:
            adapter: PlatformAdapter instance
            input_prompt: InputPrompt to resolve choices for
            context: PlatformContext dictionary for runtime API calls
            
        Returns:
            List of choice strings (static or dynamically fetched)
        """
        # Check if input_prompt has get_dynamic_choices method
        if not hasattr(input_prompt, 'get_dynamic_choices'):
            # No dynamic method, return static choices
            return input_prompt.choices or []
        
        # Build cache key
        cache_key = self._build_cache_key(adapter, input_prompt, context)
        
        # Check cache
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Call dynamic method to fetch choices
        try:
            choices = await input_prompt.get_dynamic_choices(context)
            
            # Cache result
            self._cache[cache_key] = choices
            
            return choices
        except Exception as e:
            # If dynamic resolution fails, fall back to static choices
            return input_prompt.choices or []
    
    def clear_cache(self) -> None:
        """Clear all cached choices"""
        self._cache.clear()
    
    def invalidate_cache_for_adapter(self, adapter_name: str) -> None:
        """Invalidate cache entries for specific adapter
        
        Args:
            adapter_name: Name of adapter to invalidate cache for
        """
        keys_to_remove = [
            key for key in self._cache.keys() 
            if key.startswith(f"{adapter_name}:")
        ]
        for key in keys_to_remove:
            del self._cache[key]
