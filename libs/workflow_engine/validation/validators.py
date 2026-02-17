"""Validation classes for workflow answer validation"""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, Dict, List
from ..models.entry import EntryType, EntryData
from ..models.validation import ValidationRules


@dataclass
class ValidationResult:
    """Result of validation operation"""
    is_valid: bool
    error_message: Optional[str] = None
    field_context: Optional[str] = None


class ValidationError(Exception):
    """Raised when validation fails"""
    def __init__(self, message: str, field_context: Optional[str] = None):
        self.message = message
        self.field_context = field_context
        super().__init__(f"{field_context}: {message}" if field_context else message)


class Validator(ABC):
    """Base validator class"""
    
    @abstractmethod
    def validate(self, value: Any, field_id: str) -> ValidationResult:
        """Validate a value and return result"""
        pass


class StringValidator(Validator):
    """Validator for string type answers"""
    
    def __init__(self, rules: Optional[ValidationRules] = None):
        self.rules = rules
    
    def validate(self, value: Any, field_id: str) -> ValidationResult:
        """Validate string value with optional regex"""
        if not isinstance(value, str):
            return ValidationResult(
                is_valid=False,
                error_message=f"Expected string, got {type(value).__name__}",
                field_context=field_id
            )
        
        if self.rules and self.rules.regex:
            try:
                pattern = re.compile(self.rules.regex)
                if not pattern.match(value):
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Value '{value}' does not match pattern '{self.rules.regex}'",
                        field_context=field_id
                    )
            except re.error as e:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Invalid regex pattern: {e}",
                    field_context=field_id
                )
        
        return ValidationResult(is_valid=True)


class IntegerValidator(Validator):
    """Validator for integer type answers"""
    
    def __init__(self, rules: Optional[ValidationRules] = None):
        self.rules = rules
    
    def validate(self, value: Any, field_id: str) -> ValidationResult:
        """Validate integer value with optional range"""
        if not isinstance(value, int) or isinstance(value, bool):
            return ValidationResult(
                is_valid=False,
                error_message=f"Expected integer, got {type(value).__name__}",
                field_context=field_id
            )
        
        if self.rules:
            if self.rules.min_value is not None and value < self.rules.min_value:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Value {value} is below minimum {self.rules.min_value}",
                    field_context=field_id
                )
            
            if self.rules.max_value is not None and value > self.rules.max_value:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Value {value} exceeds maximum {self.rules.max_value}",
                    field_context=field_id
                )
        
        return ValidationResult(is_valid=True)


class BooleanValidator(Validator):
    """Validator for boolean type answers"""
    
    def validate(self, value: Any, field_id: str) -> ValidationResult:
        """Validate boolean value"""
        if not isinstance(value, bool):
            return ValidationResult(
                is_valid=False,
                error_message=f"Expected boolean, got {type(value).__name__}",
                field_context=field_id
            )
        
        return ValidationResult(is_valid=True)


class ChoiceValidator(Validator):
    """Validator for choice type answers"""
    
    def __init__(self, rules: Optional[ValidationRules] = None):
        self.rules = rules
    
    def validate(self, value: Any, field_id: str) -> ValidationResult:
        """Validate choice value against enum"""
        if not isinstance(value, str):
            return ValidationResult(
                is_valid=False,
                error_message=f"Expected string choice, got {type(value).__name__}",
                field_context=field_id
            )
        
        if self.rules and self.rules.choices:
            if value not in self.rules.choices:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Value '{value}' not in allowed choices: {', '.join(self.rules.choices)}",
                    field_context=field_id
                )
        
        return ValidationResult(is_valid=True)


class CrossFieldValidator:
    """Validator for cross-field validation rules"""
    
    def __init__(self, expression_evaluator: Optional[Any] = None):
        self.expression_evaluator = expression_evaluator
    
    def validate(
        self, 
        expression: str, 
        field_id: str,
        context: Dict[str, Any]
    ) -> ValidationResult:
        """Validate using expression against multiple field values"""
        if not self.expression_evaluator:
            return ValidationResult(
                is_valid=False,
                error_message="Expression evaluator not configured",
                field_context=field_id
            )
        
        try:
            result = self.expression_evaluator.evaluate(expression, context)
            if not isinstance(result, bool):
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Expression must return boolean, got {type(result).__name__}",
                    field_context=field_id
                )
            
            if not result:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Cross-field validation failed: {expression}",
                    field_context=field_id
                )
            
            return ValidationResult(is_valid=True)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Expression evaluation error: {str(e)}",
                field_context=field_id
            )


class ValidatorFactory:
    """Factory for creating validators based on entry type"""
    
    @staticmethod
    def create_validator(
        entry_type: EntryType, 
        rules: Optional[ValidationRules] = None
    ) -> Validator:
        """Create appropriate validator for entry type"""
        validators = {
            EntryType.STRING: StringValidator,
            EntryType.INTEGER: IntegerValidator,
            EntryType.BOOLEAN: BooleanValidator,
            EntryType.CHOICE: ChoiceValidator
        }
        
        validator_class = validators.get(entry_type)
        if not validator_class:
            raise ValueError(f"No validator for type {entry_type}")
        
        if entry_type in (EntryType.STRING, EntryType.INTEGER, EntryType.CHOICE):
            return validator_class(rules)
        else:
            return validator_class()
