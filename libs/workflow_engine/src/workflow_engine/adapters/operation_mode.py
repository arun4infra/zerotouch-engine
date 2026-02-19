"""Adapter operation mode enforcement for read-only restrictions during traversal"""

from enum import Enum
from typing import Optional
from contextlib import contextmanager


class OperationType(Enum):
    """Classification of adapter operations"""
    READ = "read"      # Validation, data fetching, get_dynamic_choices
    MUTATE = "mutate"  # Resource creation, deletion, state changes


class OperationMode(Enum):
    """Execution mode for adapter operations"""
    TRAVERSAL = "traversal"    # During workflow traversal - read-only
    COMPLETION = "completion"  # After workflow completion - mutations allowed


class ReadOnlyViolationError(Exception):
    """Raised when adapter attempts mutation during traversal phase"""
    pass


class OperationModeContext:
    """Global context tracking current operation mode"""
    
    _current_mode: Optional[OperationMode] = None
    
    @classmethod
    def set_mode(cls, mode: OperationMode) -> None:
        """Set current operation mode"""
        cls._current_mode = mode
    
    @classmethod
    def get_mode(cls) -> Optional[OperationMode]:
        """Get current operation mode"""
        return cls._current_mode
    
    @classmethod
    def is_traversal_mode(cls) -> bool:
        """Check if currently in traversal mode"""
        return cls._current_mode == OperationMode.TRAVERSAL
    
    @classmethod
    def is_completion_mode(cls) -> bool:
        """Check if currently in completion mode"""
        return cls._current_mode == OperationMode.COMPLETION
    
    @classmethod
    def clear(cls) -> None:
        """Clear operation mode"""
        cls._current_mode = None


@contextmanager
def traversal_mode():
    """Context manager for traversal mode (read-only)"""
    previous_mode = OperationModeContext.get_mode()
    OperationModeContext.set_mode(OperationMode.TRAVERSAL)
    try:
        yield
    finally:
        if previous_mode:
            OperationModeContext.set_mode(previous_mode)
        else:
            OperationModeContext.clear()


@contextmanager
def completion_mode():
    """Context manager for completion mode (mutations allowed)"""
    previous_mode = OperationModeContext.get_mode()
    OperationModeContext.set_mode(OperationMode.COMPLETION)
    try:
        yield
    finally:
        if previous_mode:
            OperationModeContext.set_mode(previous_mode)
        else:
            OperationModeContext.clear()


def enforce_read_only(operation_type: OperationType) -> None:
    """Enforce read-only restriction during traversal mode
    
    Args:
        operation_type: Type of operation being performed
        
    Raises:
        ReadOnlyViolationError: If mutation attempted during traversal
    """
    if operation_type == OperationType.MUTATE and OperationModeContext.is_traversal_mode():
        raise ReadOnlyViolationError(
            "State-mutating operations are prohibited during workflow traversal. "
            "Mutations must be deferred to workflow completion phase."
        )
