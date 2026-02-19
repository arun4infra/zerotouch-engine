"""SessionStateService for workflow state management"""

from typing import Optional, Dict, Any
from workflow_engine.storage.session_store import SessionStore


class SessionStateService:
    """Service for session state management
    
    Wraps SessionStore with a service interface for managing workflow state.
    Provides methods to save, load, delete, and check existence of session state.
    
    Requirements: 3.1, 3.2, 3.3
    """
    
    def __init__(self, store: SessionStore):
        """Initialize session state service
        
        Args:
            store: SessionStore implementation for persistence
        """
        self.store = store
    
    async def save(self, session_id: str, state: Dict[str, Any]) -> None:
        """Save workflow state
        
        Args:
            session_id: Unique session identifier
            state: Workflow state dictionary to persist
            
        Raises:
            OSError: If save operation fails
        """
        await self.store.save(session_id, state)
    
    async def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load workflow state
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Workflow state dictionary if found, None otherwise
            
        Raises:
            OSError: If load operation fails
        """
        return await self.store.load(session_id)
    
    async def delete(self, session_id: str) -> None:
        """Delete workflow state
        
        Args:
            session_id: Unique session identifier
            
        Raises:
            OSError: If delete operation fails
        """
        await self.store.delete(session_id)
    
    async def exists(self, session_id: str) -> bool:
        """Check if session exists
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            True if session exists, False otherwise
        """
        state = await self.load(session_id)
        return state is not None
