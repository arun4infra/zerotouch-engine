"""Answer validator wrapper for workflow questions"""
from typing import Optional
from ..models.entry import EntryData
from ..models.workflow_dsl import QuestionNode
from .validators import ValidatorFactory, ValidationResult


class AnswerValidator:
    """Validates answers against question validation rules"""
    
    def validate(self, entry_data: EntryData, question: QuestionNode) -> bool:
        """Validate answer data against question rules
        
        Args:
            entry_data: Answer data to validate
            question: Question node with validation rules
            
        Returns:
            True if valid, False otherwise
        """
        if not question.validation:
            return True
        
        validator = ValidatorFactory.create_validator(
            entry_data.type,
            question.validation
        )
        
        result = validator.validate(entry_data.value, question.id)
        return result.is_valid
