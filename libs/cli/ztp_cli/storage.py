"""Filesystem storage for workflow sessions"""

from pathlib import Path
from typing import Dict, Any, Optional
import json
import aiofiles


class FilesystemStore:
    """Store workflow sessions in .ztc/session.json"""
    
    def __init__(self, base_path: Path = Path(".ztc")):
        """Initialize filesystem store
        
        Args:
            base_path: Base directory for session storage
        """
        self.base_path = base_path
        self.session_file = self.base_path / "session.json"
    
    async def save(self, session_id: str, state: Dict[str, Any]) -> None:
        """Save session state atomically
        
        Args:
            session_id: Session identifier
            state: Session state dictionary
        """
        # Ensure directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing sessions
        sessions = await self._load_all_sessions()
        
        # Update session
        sessions[session_id] = state
        
        # Atomic write
        temp_file = self.session_file.with_suffix(".tmp")
        async with aiofiles.open(temp_file, 'w') as f:
            await f.write(json.dumps(sessions, indent=2))
        
        # Atomic rename
        temp_file.replace(self.session_file)
    
    async def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session state
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session state dictionary or None if not found
        """
        sessions = await self._load_all_sessions()
        return sessions.get(session_id)
    
    async def delete(self, session_id: str) -> None:
        """Delete session state
        
        Args:
            session_id: Session identifier
        """
        sessions = await self._load_all_sessions()
        
        if session_id in sessions:
            del sessions[session_id]
            
            # Write updated sessions
            async with aiofiles.open(self.session_file, 'w') as f:
                await f.write(json.dumps(sessions, indent=2))
    
    async def _load_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Load all sessions from file
        
        Returns:
            Dictionary of session_id -> state
        """
        if not self.session_file.exists():
            return {}
        
        async with aiofiles.open(self.session_file, 'r') as f:
            content = await f.read()
            return json.loads(content) if content else {}
