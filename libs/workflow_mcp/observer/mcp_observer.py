"""MCP Server Observer for workflow event notifications"""
from typing import Any, Dict
from mcp import ServerSession
from mcp.types import JSONRPCNotification

from libs.workflow_engine.core.observer import (
    QuestionPathTraverserObserver,
    QuestionPathNextQuestionReady,
    QuestionPathFeedbackEntered,
    QuestionPathCompleted,
    SessionRestored
)


class MCPServerObserver(QuestionPathTraverserObserver):
    """Observer that sends workflow events as MCP notifications"""
    
    def __init__(self, session: ServerSession):
        """Initialize observer with MCP server session
        
        Args:
            session: MCP ServerSession for sending notifications
        """
        self.session = session
    
    async def receive_notification_async(
        self, 
        notification: Any
    ) -> None:
        """Convert workflow notification to MCP notification
        
        Args:
            notification: Workflow event notification
        """
        # Determine notification method and params
        method, params = self._convert_notification(notification)
        
        # Send MCP notification using official SDK
        await self.session.send_notification(
            JSONRPCNotification(
                method=method,
                params=params
            )
        )
    
    def _convert_notification(
        self, 
        notification: Any
    ) -> tuple[str, Dict[str, Any]]:
        """Convert workflow notification to MCP method and params
        
        Args:
            notification: Workflow event notification
            
        Returns:
            Tuple of (method, params) for MCP notification
        """
        if isinstance(notification, QuestionPathNextQuestionReady):
            return (
                "workflow/question_ready",
                {
                    "question_id": notification.current_question.id,
                    "question_type": notification.current_question.type.value,
                    "prompt": notification.current_question.prompt,
                    "sensitive": notification.current_question.sensitive
                }
            )
        
        elif isinstance(notification, QuestionPathFeedbackEntered):
            return (
                "workflow/answer_submitted",
                {
                    "feedback_id": notification.feedback.feedback_id,
                    "question_id": notification.feedback.entry.id,
                    "is_automatic": notification.feedback.is_automatic,
                    "is_sensitive": notification.feedback.is_sensitive,
                    "is_new": notification.is_new_feedback
                }
            )
        
        elif isinstance(notification, QuestionPathCompleted):
            return (
                "workflow/completed",
                {
                    "reason": notification.reason.value
                }
            )
        
        elif isinstance(notification, SessionRestored):
            return (
                "workflow/session_restored",
                {
                    "session_id": notification.session_id,
                    "feedback_count": notification.feedback_count
                }
            )
        
        else:
            # Unknown notification type
            return (
                "workflow/unknown_event",
                {
                    "type": type(notification).__name__
                }
            )
