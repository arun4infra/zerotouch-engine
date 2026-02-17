"""Level tracker for workflow navigation state"""
from dataclasses import dataclass
from typing import List, Dict, Any
from .entry import Entry


@dataclass
class QuestionPathLevelTracker:
    """Track position within a single workflow level"""
    stopped_at_entry: Entry
    stopped_at_entry_index: int
    level_entries: List[Entry]
    planning_context: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize level tracker state"""
        return {
            "stopped_at_entry": self.stopped_at_entry.to_dict(),
            "stopped_at_entry_index": self.stopped_at_entry_index,
            "level_entries": [entry.to_dict() for entry in self.level_entries],
            "planning_context": self.planning_context
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuestionPathLevelTracker':
        """Deserialize level tracker state"""
        return cls(
            stopped_at_entry=Entry.from_dict(data["stopped_at_entry"]),
            stopped_at_entry_index=data["stopped_at_entry_index"],
            level_entries=[Entry.from_dict(e) for e in data["level_entries"]],
            planning_context=data["planning_context"]
        )
