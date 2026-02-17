"""Observer pattern for workflow events"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional
from enum import Enum
from ..models.entry import Entry
from ..models.feedback import QuestionPathFeedback


class QuestionPathCompletedReason(Enum):
    """Reason for workflow completion"""
    CLOSED = "closed"  # Normal completion
    CANCELED = "canceled"  # User canceled


@dataclass
class QuestionPathNextQuestionReady:
    """Emitted when next question requires user input"""
    current_question: Entry
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize notification to dict"""
        return {
            "type": "QuestionPathNextQuestionReady",
            "current_question": self.current_question.to_dict()
        }


@dataclass
class QuestionPathFeedbackEntered:
    """Emitted when answer is submitted"""
    feedback: QuestionPathFeedback
    is_new_feedback: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize notification to dict with secret redaction"""
        return {
            "type": "QuestionPathFeedbackEntered",
            "feedback": self.feedback.to_dict(redact_secrets=True),
            "is_new_feedback": self.is_new_feedback
        }


@dataclass
class QuestionPathFeedbackUpdated:
    """Emitted when current answer is modified"""
    feedback: QuestionPathFeedback
    is_new_feedback: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize notification to dict with secret redaction"""
        return {
            "type": "QuestionPathFeedbackUpdated",
            "feedback": self.feedback.to_dict(redact_secrets=True),
            "is_new_feedback": self.is_new_feedback
        }


@dataclass
class QuestionPathCompleted:
    """Emitted when workflow completes"""
    reason: QuestionPathCompletedReason
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize notification to dict"""
        return {
            "type": "QuestionPathCompleted",
            "reason": self.reason.value
        }


@dataclass
class SessionRestored:
    """Emitted when session is restored"""
    session_id: str
    feedback_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize notification to dict"""
        return {
            "type": "SessionRestored",
            "session_id": self.session_id,
            "feedback_count": self.feedback_count
        }


# Union type for all notification types
QuestionPathTraverserNotification = (
    QuestionPathNextQuestionReady |
    QuestionPathFeedbackEntered |
    QuestionPathFeedbackUpdated |
    QuestionPathCompleted |
    SessionRestored
)


class QuestionPathTraverserObserver(ABC):
    """Abstract base class for workflow event observers"""
    
    @abstractmethod
    async def receive_notification_async(
        self, 
        notification: QuestionPathTraverserNotification
    ) -> None:
        """Handle notification from traverser
        
        Args:
            notification: Event notification from traverser
        """
        pass
