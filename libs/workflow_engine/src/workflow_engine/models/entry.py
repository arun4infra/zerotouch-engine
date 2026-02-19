"""Entry and EntryData models for workflow questions and answers"""
from dataclasses import dataclass
from typing import Any, Optional, Dict
from enum import Enum


class EntryType(str, Enum):
    """Question types supported by workflow engine"""
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    CHOICE = "choice"


@dataclass
class Entry:
    """Represents a workflow question"""
    id: str
    type: EntryType
    prompt: str
    help_text: Optional[str] = None
    default: Optional[Any] = None
    automatic_answer: Optional[str] = None
    sensitive: bool = False
    env_var_name: Optional[str] = None
    child_workflow_id: Optional[str] = None
    child_workflow_condition: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize entry to dictionary"""
        return {
            "id": self.id,
            "type": self.type.value,
            "prompt": self.prompt,
            "help_text": self.help_text,
            "default": self.default,
            "automatic_answer": self.automatic_answer,
            "sensitive": self.sensitive,
            "env_var_name": self.env_var_name,
            "child_workflow_id": self.child_workflow_id,
            "child_workflow_condition": self.child_workflow_condition
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Entry':
        """Deserialize entry from dictionary"""
        return cls(
            id=data["id"],
            type=EntryType(data["type"]),
            prompt=data["prompt"],
            help_text=data.get("help_text"),
            default=data.get("default"),
            automatic_answer=data.get("automatic_answer"),
            sensitive=data.get("sensitive", False),
            env_var_name=data.get("env_var_name"),
            child_workflow_id=data.get("child_workflow_id"),
            child_workflow_condition=data.get("child_workflow_condition")
        )


@dataclass
class EntryData:
    """Represents an answer to a workflow question"""
    type: EntryType
    value: Any
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize entry data to dictionary"""
        return {
            "type": self.type.value,
            "value": self.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EntryData':
        """Deserialize entry data from dictionary"""
        return cls(
            type=EntryType(data["type"]),
            value=data["value"]
        )
    
    def __eq__(self, other: object) -> bool:
        """Compare entry data for equality"""
        if not isinstance(other, EntryData):
            return False
        return self.type == other.type and self.value == other.value
