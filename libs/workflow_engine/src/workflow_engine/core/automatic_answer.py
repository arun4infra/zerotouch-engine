"""Automatic answer provider for skipping questions with pre-determined values"""
from typing import Optional, Dict, Any
from ..models.entry import Entry, EntryData, EntryType


class ExpressionError(Exception):
    """Raised when automatic answer expression evaluation fails"""
    pass


class ExpressionEvaluator:
    """Evaluates automatic answer expressions against previous answers"""
    
    def __init__(self, feedback_context: Dict[str, Any]):
        """Initialize evaluator with feedback context
        
        Args:
            feedback_context: Dictionary mapping question IDs to answer values
        """
        self.context = feedback_context
    
    async def evaluate(self, expression: str) -> Any:
        """Evaluate expression against context
        
        Args:
            expression: Expression string to evaluate
            
        Returns:
            Evaluated result
            
        Raises:
            ExpressionError: If expression evaluation fails
        """
        try:
            # Simple expression evaluation using context
            # Supports: ${question_id}, literal values, basic operations
            if expression.startswith("${") and expression.endswith("}"):
                # Variable reference: ${question_id}
                var_name = expression[2:-1]
                if var_name not in self.context:
                    raise ExpressionError(f"Variable not found: {var_name}")
                return self.context[var_name]
            else:
                # Literal value
                return expression
        except Exception as e:
            raise ExpressionError(f"Failed to evaluate expression '{expression}': {str(e)}")
    
    async def evaluate_async(self, expression: str) -> Any:
        """Async version of evaluate for consistency
        
        Args:
            expression: Expression string to evaluate
            
        Returns:
            Evaluated result
            
        Raises:
            ExpressionError: If expression evaluation fails
        """
        return await self.evaluate(expression)


class AutomaticAnswerProvider:
    """Determines if question should be auto-answered"""
    
    def __init__(self, feedback_context: Dict[str, Any]):
        """Initialize provider with feedback context
        
        Args:
            feedback_context: Dictionary mapping question IDs to answer values
        """
        self.feedback_context = feedback_context
        self.evaluator = ExpressionEvaluator(feedback_context)
    
    async def get_automatic_answer_async(self, entry: Entry) -> Optional[EntryData]:
        """Get automatic answer if configured
        
        Args:
            entry: Entry to check for automatic answer
            
        Returns:
            EntryData if automatic answer available, None otherwise
        """
        if not entry.automatic_answer:
            return None
        
        try:
            # Evaluate expression against previous answers
            result = await self.evaluator.evaluate(entry.automatic_answer)
            
            # Convert result to appropriate EntryData type
            return self._convert_to_entry_data(result, entry.type)
        except ExpressionError:
            # Expression failed, present question to user
            return None
    
    def _convert_to_entry_data(self, value: Any, entry_type: EntryType) -> EntryData:
        """Convert evaluated value to EntryData with type checking
        
        Args:
            value: Evaluated value
            entry_type: Expected entry type
            
        Returns:
            EntryData with converted value
            
        Raises:
            ExpressionError: If value cannot be converted to expected type
        """
        try:
            if entry_type == EntryType.STRING:
                return EntryData(type=EntryType.STRING, value=str(value))
            elif entry_type == EntryType.INTEGER:
                return EntryData(type=EntryType.INTEGER, value=int(value))
            elif entry_type == EntryType.BOOLEAN:
                if isinstance(value, bool):
                    return EntryData(type=EntryType.BOOLEAN, value=value)
                elif isinstance(value, str):
                    return EntryData(type=EntryType.BOOLEAN, value=value.lower() in ("true", "yes", "1"))
                else:
                    return EntryData(type=EntryType.BOOLEAN, value=bool(value))
            elif entry_type == EntryType.CHOICE:
                return EntryData(type=EntryType.CHOICE, value=str(value))
            else:
                raise ExpressionError(f"Unsupported entry type: {entry_type}")
        except (ValueError, TypeError) as e:
            raise ExpressionError(f"Cannot convert value '{value}' to type {entry_type}: {str(e)}")
