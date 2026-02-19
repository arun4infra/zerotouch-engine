"""Adapter question translator for InputPrompt to QuestionNode conversion"""

from typing import Optional, Dict, Any
from workflow_engine.adapters.base import InputPrompt
from workflow_engine.models.workflow_dsl import QuestionNode
from workflow_engine.models.validation import ValidationRules


class AdapterQuestionTranslator:
    """Translates PlatformAdapter InputPrompt objects to Workflow DSL QuestionNode"""
    
    def translate_input_prompt(
        self, 
        prompt: InputPrompt,
        adapter_name: str
    ) -> QuestionNode:
        """Convert InputPrompt to QuestionNode
        
        Args:
            prompt: InputPrompt from adapter
            adapter_name: Name of the adapter (for ID prefixing)
            
        Returns:
            QuestionNode for workflow DSL
        """
        return QuestionNode(
            id=f"{adapter_name}.{prompt.name}",
            type=self._map_type(prompt.type),
            prompt=prompt.prompt,
            help_text=prompt.help_text,
            default=prompt.default,
            validation=self._build_validation(prompt),
            sensitive=prompt.type == "password"
        )
    
    def _map_type(self, prompt_type: str) -> str:
        """Map InputPrompt type to workflow DSL type
        
        Args:
            prompt_type: InputPrompt type (string, password, choice, integer, boolean, json)
            
        Returns:
            Workflow DSL type (string, integer, boolean, choice)
        """
        mapping = {
            "string": "string",
            "password": "string",  # Password is string with sensitive flag
            "choice": "choice",
            "integer": "integer",
            "boolean": "boolean",
            "json": "string"  # JSON is stored as string
        }
        return mapping.get(prompt_type, "string")
    
    def _build_validation(self, prompt: InputPrompt) -> Optional[ValidationRules]:
        """Build validation rules from InputPrompt
        
        Args:
            prompt: InputPrompt with validation info
            
        Returns:
            ValidationRules or None if no validation
        """
        if not prompt.validation and not prompt.choices:
            return None
        
        return ValidationRules(
            regex=prompt.validation if prompt.validation else None,
            choices=prompt.choices if prompt.choices else None
        )
    
    def merge_adapter_answers(
        self,
        adapter_answers: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Merge answers from multiple adapters for cross-adapter accessibility
        
        Creates a unified context where each adapter can access answers from other
        adapters. This supports cross-adapter dependencies (Requirement 9.5, 9.6).
        
        Args:
            adapter_answers: Dictionary mapping adapter names to their answer dictionaries
            
        Returns:
            Merged context with all adapter answers accessible
        """
        # Return the adapter_answers structure as-is for cross-adapter access
        # Each adapter can access other adapters' answers via adapter_answers[adapter_name][field]
        return adapter_answers
