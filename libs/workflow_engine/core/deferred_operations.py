"""Deferred operations registry for workflow completion actions"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from ..models.feedback import QuestionPathFeedback


@dataclass
class OnQuestionPathCompleteOperation(ABC):
    """Abstract base class for deferred operations executed on workflow completion"""
    feedback_id: int
    
    @abstractmethod
    async def execute(
        self, 
        feedback_history: List[QuestionPathFeedback],
        platform_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Execute operation with access to feedback history and context
        
        Secrets are resolved at execution time from environment variables.
        
        Args:
            feedback_history: Complete list of feedback records
            platform_context: Optional platform context with resolved secrets
            
        Raises:
            Exception: If operation execution fails
        """
        pass
    
    @abstractmethod
    def rollback(self) -> None:
        """Rollback operation on failure
        
        This method should undo any side effects of the execute() method.
        Should not raise exceptions - log errors instead.
        """
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize operation to dictionary for session persistence
        
        Returns:
            Dictionary containing operation type and data
        """
        return {
            "type": self.__class__.__name__,
            "feedback_id": self.feedback_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OnQuestionPathCompleteOperation':
        """Deserialize operation from dictionary
        
        Args:
            data: Dictionary containing operation data
            
        Returns:
            Reconstructed operation instance
            
        Raises:
            ValueError: If operation type is unknown
        """
        # This is a base implementation - subclasses should override
        raise NotImplementedError(f"Deserialization not implemented for {cls.__name__}")


class DeferredOperationsRegistry:
    """Registry for operations that execute on workflow completion"""
    
    def __init__(self):
        """Initialize empty operations registry"""
        self.operations: List[OnQuestionPathCompleteOperation] = []
    
    def register(self, operation: OnQuestionPathCompleteOperation) -> None:
        """Register deferred operation for execution on workflow completion
        
        Args:
            operation: Operation to register
        """
        self.operations.append(operation)
    
    async def execute_all(
        self, 
        feedback_history: List[QuestionPathFeedback],
        platform_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Execute all registered operations in registration order
        
        Resolves secrets in platform_context before execution.
        
        Args:
            feedback_history: Complete feedback history from workflow
            platform_context: Optional platform context (secrets resolved at runtime)
            
        Raises:
            Exception: If any operation fails (triggers rollback)
        """
        from ..secrets import SecretResolver
        
        # Resolve secrets in platform context at execution time
        resolved_context = None
        if platform_context:
            resolved_context = SecretResolver.resolve_context_secrets(platform_context)
        
        executed_operations: List[OnQuestionPathCompleteOperation] = []
        
        try:
            for operation in self.operations:
                await operation.execute(feedback_history, resolved_context)
                executed_operations.append(operation)
        except Exception as e:
            # Rollback all executed operations in reverse order
            for op in reversed(executed_operations):
                try:
                    op.rollback()
                except Exception as rollback_error:
                    # Log rollback errors but continue rolling back
                    print(f"Rollback failed for {op.__class__.__name__}: {rollback_error}")
            
            # Re-raise original exception with operation details
            raise Exception(
                f"Deferred operation failed: {operation.__class__.__name__} "
                f"(feedback_id={operation.feedback_id})"
            ) from e
    
    def rollback_all(self) -> None:
        """Rollback all registered operations without execution
        
        This is called when workflow is canceled before completion.
        Operations are rolled back in reverse registration order.
        """
        for operation in reversed(self.operations):
            try:
                operation.rollback()
            except Exception as e:
                # Log rollback errors but continue
                print(f"Rollback failed for {operation.__class__.__name__}: {e}")
    
    def clear(self) -> None:
        """Clear all registered operations
        
        This discards all operations without execution or rollback.
        Used when workflow is canceled.
        """
        self.operations.clear()
    
    def serialize(self) -> List[Dict[str, Any]]:
        """Serialize all registered operations for session persistence
        
        Returns:
            List of serialized operation dictionaries
        """
        return [op.to_dict() for op in self.operations]
    
    def restore(self, operations_data: List[Dict[str, Any]]) -> None:
        """Restore operations from serialized data
        
        Args:
            operations_data: List of serialized operation dictionaries
            
        Note:
            This requires operation types to implement from_dict() classmethod
        """
        self.operations.clear()
        for op_data in operations_data:
            # Operation deserialization requires registry of operation types
            # For now, store raw data - actual restoration happens in subclasses
            pass
    
    def __len__(self) -> int:
        """Get count of registered operations"""
        return len(self.operations)
    
    def __iter__(self):
        """Iterate over registered operations"""
        return iter(self.operations)
