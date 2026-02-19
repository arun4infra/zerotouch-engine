"""Feedback system for tracking user answers"""
from dataclasses import dataclass
from typing import Dict, Any
from .entry import Entry, EntryData


@dataclass(frozen=True)
class QuestionPathFeedback:
    """Immutable record of user answer with context"""
    feedback_id: int
    timestamp: int
    entry: Entry
    entry_data: EntryData
    is_automatic: bool = False
    is_sensitive: bool = False
    
    def equals(self, other_data: EntryData) -> bool:
        """Compare answer data for equality"""
        return self.entry_data == other_data
    
    def to_dict(self, redact_secrets: bool = False) -> Dict[str, Any]:
        """Serialize feedback to JSON-compatible dict
        
        Args:
            redact_secrets: If True, mask sensitive values for logging/display
            
        Returns:
            Dictionary with feedback data
        """
        from ..secrets import SecretResolver
        
        entry_data_dict = self.entry_data.to_dict()
        
        # For sensitive fields, store env var reference or redact
        if self.is_sensitive:
            if redact_secrets:
                # Mask for logging/display
                entry_data_dict["value"] = SecretResolver.mask_sensitive_value(
                    str(entry_data_dict["value"])
                )
            elif self.entry.env_var_name:
                # Store as env var reference for serialization
                entry_data_dict["value"] = SecretResolver.create_secret_reference(
                    self.entry.env_var_name
                )
        
        return {
            "feedback_id": self.feedback_id,
            "timestamp": self.timestamp,
            "entry": self.entry.to_dict(),
            "entry_data": entry_data_dict,
            "is_automatic": self.is_automatic,
            "is_sensitive": self.is_sensitive
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuestionPathFeedback':
        """Deserialize feedback from dict
        
        Resolves environment variable references for sensitive fields.
        """
        from ..secrets import SecretResolver
        
        entry = Entry.from_dict(data["entry"])
        entry_data_dict = data["entry_data"]
        
        # Resolve secret references for sensitive fields
        if data.get("is_sensitive", False) and SecretResolver.is_secret_reference(
            entry_data_dict.get("value")
        ):
            resolved_value = SecretResolver.resolve_secret(
                entry_data_dict["value"],
                entry.id
            )
            entry_data_dict = {**entry_data_dict, "value": resolved_value}
        
        return cls(
            feedback_id=data["feedback_id"],
            timestamp=data["timestamp"],
            entry=entry,
            entry_data=EntryData.from_dict(entry_data_dict),
            is_automatic=data.get("is_automatic", False),
            is_sensitive=data.get("is_sensitive", False)
        )
