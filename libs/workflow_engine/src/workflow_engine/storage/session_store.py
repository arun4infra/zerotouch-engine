"""SessionStore abstract base class and implementations"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional
import json
import aiofiles


class SessionStore(ABC):
    """Abstract interface for session persistence"""
    
    @abstractmethod
    async def save(self, session_id: str, state: Dict[str, Any]) -> None:
        """Save session state
        
        Args:
            session_id: Unique session identifier
            state: Session state dictionary to persist
        """
        pass
    
    @abstractmethod
    async def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session state
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Session state dictionary if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def delete(self, session_id: str) -> None:
        """Delete session state
        
        Args:
            session_id: Unique session identifier
        """
        pass


class FilesystemStore(SessionStore):
    """SessionStore implementation using filesystem persistence"""
    
    def __init__(self, base_path: Path = Path(".ztc")):
        """Initialize filesystem store
        
        Args:
            base_path: Base directory for session storage (default: .ztc)
        """
        self.base_path = base_path
    
    async def save(self, session_id: str, state: Dict[str, Any]) -> None:
        """Atomic write to .ztc/session.json
        
        Uses temporary file and atomic rename to ensure no partial writes.
        
        Args:
            session_id: Unique session identifier
            state: Session state dictionary to persist
            
        Raises:
            OSError: If file operations fail
        """
        # Ensure base directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        session_file = self.base_path / "session.json"
        temp_file = self.base_path / "session.json.tmp"
        
        try:
            # Write to temp file
            async with aiofiles.open(temp_file, 'w') as f:
                await f.write(json.dumps(state, indent=2))
            
            # Atomic rename
            temp_file.replace(session_file)
        except Exception as e:
            # Clean up temp file on error
            if temp_file.exists():
                temp_file.unlink()
            raise OSError(f"Failed to save session {session_id}: {e}") from e
    
    async def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session state from .ztc/session.json
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Session state dictionary if found, None otherwise
            
        Raises:
            OSError: If file read fails
            json.JSONDecodeError: If file contains invalid JSON
        """
        session_file = self.base_path / "session.json"
        
        if not session_file.exists():
            return None
        
        try:
            async with aiofiles.open(session_file, 'r') as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            raise OSError(f"Failed to load session {session_id}: {e}") from e
    
    async def delete(self, session_id: str) -> None:
        """Delete session state file
        
        Args:
            session_id: Unique session identifier
            
        Raises:
            OSError: If file deletion fails
        """
        session_file = self.base_path / "session.json"
        
        if session_file.exists():
            try:
                session_file.unlink()
            except Exception as e:
                raise OSError(f"Failed to delete session {session_id}: {e}") from e


class InMemoryStore(SessionStore):
    """SessionStore implementation for testing without filesystem dependencies"""
    
    def __init__(self):
        """Initialize in-memory store"""
        self._storage: Dict[str, Dict[str, Any]] = {}
    
    async def save(self, session_id: str, state: Dict[str, Any]) -> None:
        """Save session state in memory
        
        Args:
            session_id: Unique session identifier
            state: Session state dictionary to persist
        """
        self._storage[session_id] = state.copy()
    
    async def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session state from memory
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Session state dictionary if found, None otherwise
        """
        return self._storage.get(session_id)
    
    async def delete(self, session_id: str) -> None:
        """Delete session state from memory
        
        Args:
            session_id: Unique session identifier
        """
        self._storage.pop(session_id, None)
