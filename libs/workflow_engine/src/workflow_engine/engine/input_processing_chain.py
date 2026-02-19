"""Input processing handlers using Chain of Responsibility pattern"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ProcessingResult:
    """Result of input processing"""
    handled: bool
    value: Any = None
    display_message: Optional[str] = None  # For auto-derived/auto-selected messages
    skip_to_next: bool = False


class InputProcessingHandler(ABC):
    """Base handler in the chain of responsibility"""
    
    def __init__(self):
        self._next_handler: Optional[InputProcessingHandler] = None
    
    def set_next(self, handler: 'InputProcessingHandler') -> 'InputProcessingHandler':
        """Set the next handler in the chain"""
        self._next_handler = handler
        return handler
    
    def handle(self, field_name: str, input_def: dict, adapter, collected_config: dict) -> ProcessingResult:
        """Process the input or pass to next handler"""
        result = self._process(field_name, input_def, adapter, collected_config)
        
        if result.handled:
            return result
        
        if self._next_handler:
            return self._next_handler.handle(field_name, input_def, adapter, collected_config)
        
        # No handler processed it - should not happen if chain is complete
        return ProcessingResult(handled=False)
    
    @abstractmethod
    def _process(self, field_name: str, input_def: dict, adapter, collected_config: dict) -> ProcessingResult:
        """Implement specific processing logic"""
        pass


class SkipFieldHandler(InputProcessingHandler):
    """Handler that checks if field should be skipped"""
    
    def _process(self, field_name: str, input_def: dict, adapter, collected_config: dict) -> ProcessingResult:
        if hasattr(adapter, 'should_skip_field') and adapter.should_skip_field(field_name, collected_config):
            return ProcessingResult(handled=True, skip_to_next=True)
        return ProcessingResult(handled=False)


class DefaultValueHandler(InputProcessingHandler):
    """Handler that auto-selects fields with default values"""
    
    def _process(self, field_name: str, input_def: dict, adapter, collected_config: dict) -> ProcessingResult:
        default_value = input_def.get("default")
        if default_value is not None:
            prompt = input_def.get("prompt", field_name)
            return ProcessingResult(
                handled=True,
                value=default_value,
                display_message=f"{prompt}: {default_value} (auto-selected)"
            )
        return ProcessingResult(handled=False)


class DerivedValueHandler(InputProcessingHandler):
    """Handler that derives field values from other fields"""
    
    def _process(self, field_name: str, input_def: dict, adapter, collected_config: dict) -> ProcessingResult:
        if hasattr(adapter, 'derive_field_value'):
            derived_value = adapter.derive_field_value(field_name, collected_config)
            if derived_value is not None:
                prompt = input_def.get("prompt", field_name)
                return ProcessingResult(
                    handled=True,
                    value=derived_value,
                    display_message=f"{prompt}: {derived_value} (auto-derived)"
                )
        return ProcessingResult(handled=False)


class PromptUserHandler(InputProcessingHandler):
    """Final handler that prompts user for input"""
    
    def _process(self, field_name: str, input_def: dict, adapter, collected_config: dict) -> ProcessingResult:
        # This handler always "handles" by indicating user prompt is needed
        return ProcessingResult(handled=True, value=None)


class InputProcessingChain:
    """Orchestrates the chain of input processing handlers"""
    
    def __init__(self):
        # Build the chain
        self.skip_handler = SkipFieldHandler()
        self.default_handler = DefaultValueHandler()
        self.derived_handler = DerivedValueHandler()
        self.prompt_handler = PromptUserHandler()
        
        # Link handlers
        self.skip_handler.set_next(self.default_handler) \
                        .set_next(self.derived_handler) \
                        .set_next(self.prompt_handler)
    
    def process(self, field_name: str, input_def: dict, adapter, collected_config: dict) -> ProcessingResult:
        """Process input through the handler chain"""
        return self.skip_handler.handle(field_name, input_def, adapter, collected_config)
