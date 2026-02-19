"""QuestionPathTraverser for stateful workflow navigation"""
from typing import Optional, List, Dict, Any
import hashlib
import json
from ..models.entry import Entry, EntryData
from ..models.feedback import QuestionPathFeedback
from ..models.level_tracker import QuestionPathLevelTracker
from .observer import (
    QuestionPathTraverserObserver,
    QuestionPathNextQuestionReady,
    QuestionPathFeedbackEntered,
    QuestionPathCompleted,
    QuestionPathCompletedReason,
    SessionRestored
)
from .automatic_answer import AutomaticAnswerProvider
from .deferred_operations import DeferredOperationsRegistry, OnQuestionPathCompleteOperation
from ..adapters.dynamic_choices import DynamicChoiceResolver


class QuestionPathTraverser:
    """Stateful navigation component managing workflow traversal with level tracking"""
    
    def __init__(
        self,
        entries: List[Entry],
        planning_context: Optional[Dict[str, Any]] = None,
        workflow_version_hash: Optional[str] = None,
        workflow_loader: Optional[Any] = None
    ):
        """Initialize traverser with workflow entries
        
        Args:
            entries: List of Entry objects representing workflow questions
            planning_context: Optional context dictionary for workflow execution
            workflow_version_hash: SHA256 hash of workflow DSL for version tracking
            workflow_loader: Optional loader for child workflows
        """
        self.entries = entries
        self.planning_context = planning_context or {}
        self.workflow_version_hash = workflow_version_hash or self._compute_workflow_hash()
        self.workflow_loader = workflow_loader
        
        # Current question state
        self.current_question: Optional[Entry] = None
        self.current_entry_index: int = 0
        
        # Feedback history with monotonic ID generation
        self.current_feedback_id: int = 0
        self.feedback_map: Dict[int, QuestionPathFeedback] = {}
        
        # Level tracking for nested workflows
        self.current_level: Optional[QuestionPathLevelTracker] = None
        self.level_stack: List[QuestionPathLevelTracker] = []
        
        # Deferred operations registry
        self.deferred_operations_registry = DeferredOperationsRegistry()
        
        # Observer pattern for event notifications
        self._observers: List[QuestionPathTraverserObserver] = []
        
        # Automatic answer provider
        self._automatic_answer_provider: Optional[AutomaticAnswerProvider] = None
        
        # Dynamic choice resolver
        self._dynamic_choice_resolver = DynamicChoiceResolver()
    
    def register_deferred_operation(self, operation: OnQuestionPathCompleteOperation) -> None:
        """Register deferred operation for execution on workflow completion
        
        Args:
            operation: Operation to register
        """
        self.deferred_operations_registry.register(operation)
    
    async def execute_deferred_operations(
        self, 
        platform_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Execute all registered deferred operations
        
        Args:
            platform_context: Optional platform context for operations
            
        Raises:
            Exception: If any operation fails (triggers rollback)
        """
        feedback_history = self.get_feedback_array()
        await self.deferred_operations_registry.execute_all(feedback_history, platform_context)
    
    def cancel_deferred_operations(self) -> None:
        """Cancel all deferred operations without execution
        
        This clears all registered operations when workflow is canceled.
        """
        self.deferred_operations_registry.clear()
    
    def register_observer(self, observer: QuestionPathTraverserObserver) -> None:
        """Register observer for workflow events"""
        if observer not in self._observers:
            self._observers.append(observer)
    
    def deregister_observer(self, observer: QuestionPathTraverserObserver) -> None:
        """Deregister observer from workflow events"""
        if observer in self._observers:
            self._observers.remove(observer)
    
    async def _notify_observers(self, notification: Any) -> None:
        """Notify all registered observers of event"""
        for observer in self._observers:
            await observer.receive_notification_async(notification)
    
    def _compute_workflow_hash(self) -> str:
        """Compute SHA256 hash of workflow structure"""
        workflow_data = json.dumps([e.to_dict() for e in self.entries], sort_keys=True)
        return hashlib.sha256(workflow_data.encode()).hexdigest()
    
    def _get_feedback_context(self) -> Dict[str, Any]:
        """Build feedback context for automatic answer evaluation
        
        Returns:
            Dictionary mapping question IDs to answer values
        """
        context = {}
        for feedback in self.get_feedback_array():
            context[feedback.entry.id] = feedback.entry_data.value
        return context
    
    def _update_automatic_answer_provider(self) -> None:
        """Update automatic answer provider with current feedback context"""
        feedback_context = self._get_feedback_context()
        self._automatic_answer_provider = AutomaticAnswerProvider(feedback_context)
    
    async def _process_automatic_answers(self, timestamp: int) -> None:
        """Process automatic answers and skip questions
        
        Args:
            timestamp: Current timestamp for feedback records
        """
        while self.current_question and self.current_question.automatic_answer:
            # Update provider with latest feedback
            self._update_automatic_answer_provider()
            
            # Try to get automatic answer
            auto_answer = await self._automatic_answer_provider.get_automatic_answer_async(
                self.current_question
            )
            
            if auto_answer is None:
                # Expression failed, present question to user
                break
            
            # Create feedback with auto-answer flag
            feedback = QuestionPathFeedback(
                feedback_id=self.current_feedback_id,
                timestamp=timestamp,
                entry=self.current_question,
                entry_data=auto_answer,
                is_automatic=True,
                is_sensitive=self.current_question.sensitive
            )
            
            # Store feedback
            self.feedback_map[self.current_feedback_id] = feedback
            self.current_feedback_id += 1
            
            # Notify observers
            await self._notify_observers(
                QuestionPathFeedbackEntered(feedback=feedback, is_new_feedback=True)
            )
            
            # Check if current question has child workflow
            if await self._should_enter_child_workflow(self.current_question):
                await self._enter_child_workflow(self.current_question, timestamp)
                return
            
            # Advance to next question
            self.current_entry_index += 1
            
            if self.current_entry_index < len(self.entries):
                self.current_question = self.entries[self.current_entry_index]
                
                # Update current level tracking
                if self.current_level:
                    self.current_level = QuestionPathLevelTracker(
                        stopped_at_entry=self.current_question,
                        stopped_at_entry_index=self.current_entry_index,
                        level_entries=self.current_level.level_entries,
                        planning_context=self.current_level.planning_context
                    )
            else:
                # Current level complete, check if in child workflow
                if self.level_stack:
                    await self._complete_child_workflow(timestamp)
                else:
                    # Workflow complete
                    self.current_question = None
                    await self._notify_observers(
                        QuestionPathCompleted(reason=QuestionPathCompletedReason.CLOSED)
                    )
                break
    
    async def start_async(self, timestamp: int) -> None:
        """Start traversal and initialize to first question
        
        Args:
            timestamp: Current timestamp for feedback records
        """
        if not self.entries:
            return
        
        # Initialize current level
        self.current_question = self.entries[0]
        self.current_entry_index = 0
        self.current_level = QuestionPathLevelTracker(
            stopped_at_entry=self.current_question,
            stopped_at_entry_index=0,
            level_entries=self.entries,
            planning_context=self.planning_context
        )
        
        # Process automatic answers
        await self._process_automatic_answers(timestamp)
        
        # Notify observers of first question requiring user input
        if self.current_question:
            await self._notify_observers(
                QuestionPathNextQuestionReady(current_question=self.current_question)
            )
    
    def get_current_question(self) -> Optional[Entry]:
        """Get current question requiring user input
        
        Returns:
            Current Entry or None if workflow complete
        """
        return self.current_question
    
    async def resolve_dynamic_choices_for_current_question(
        self,
        adapter: Optional[Any] = None,
        input_prompt: Optional[Any] = None
    ) -> List[str]:
        """Resolve dynamic choices for current question if applicable
        
        Args:
            adapter: Optional PlatformAdapter instance
            input_prompt: Optional InputPrompt instance
            
        Returns:
            List of choices (static or dynamically resolved)
        """
        if not adapter or not input_prompt:
            return []
        
        # Build platform context from feedback history
        platform_context = self.build_platform_context()
        
        # Resolve choices using dynamic choice resolver
        return await self._dynamic_choice_resolver.resolve_choices(
            adapter, 
            input_prompt, 
            platform_context
        )
    
    async def answer_current_question_async(
        self, 
        entry_data: EntryData, 
        timestamp: int
    ) -> None:
        """Answer current question and advance to next
        
        Args:
            entry_data: Answer data for current question
            timestamp: Current timestamp for feedback record
        """
        if not self.current_question:
            return
        
        # Create immutable feedback record with monotonic ID
        feedback = QuestionPathFeedback(
            feedback_id=self.current_feedback_id,
            timestamp=timestamp,
            entry=self.current_question,
            entry_data=entry_data,
            is_automatic=False,
            is_sensitive=self.current_question.sensitive
        )
        
        # Store feedback in map
        self.feedback_map[self.current_feedback_id] = feedback
        self.current_feedback_id += 1
        
        # Notify observers of answer submission
        await self._notify_observers(
            QuestionPathFeedbackEntered(feedback=feedback, is_new_feedback=True)
        )
        
        # Check if current question has child workflow
        if await self._should_enter_child_workflow(self.current_question):
            await self._enter_child_workflow(self.current_question, timestamp)
            return
        
        # Advance to next question
        await self._advance_to_next_question(timestamp)
    
    async def _should_enter_child_workflow(self, entry: Entry) -> bool:
        """Check if entry has child workflow and condition is met
        
        Args:
            entry: Entry to check for child workflow
            
        Returns:
            True if should enter child workflow
        """
        if not entry.child_workflow_id:
            return False
        
        # If no condition, always enter
        if not entry.child_workflow_condition:
            return True
        
        # Evaluate condition
        self._update_automatic_answer_provider()
        try:
            from ..core.automatic_answer import ExpressionEvaluator
            evaluator = ExpressionEvaluator(self._get_feedback_context())
            result = await evaluator.evaluate_async(entry.child_workflow_condition)
            return bool(result)
        except Exception:
            return False
    
    async def _enter_child_workflow(self, entry: Entry, timestamp: int) -> None:
        """Enter child workflow by pushing current level to stack
        
        Args:
            entry: Entry with child workflow reference
            timestamp: Current timestamp
        """
        if not self.workflow_loader or not entry.child_workflow_id:
            return
        
        # Push current level to stack
        if self.current_level:
            self.level_stack.append(self.current_level)
        
        # Load child workflow entries
        child_entries = await self.workflow_loader.load_workflow(entry.child_workflow_id)
        
        # Inherit parent context
        child_context = self.planning_context.copy()
        
        # Initialize new level for child workflow
        if child_entries:
            self.entries = child_entries
            self.current_entry_index = 0
            self.current_question = child_entries[0]
            
            self.current_level = QuestionPathLevelTracker(
                stopped_at_entry=self.current_question,
                stopped_at_entry_index=0,
                level_entries=child_entries,
                planning_context=child_context
            )
            
            # Process automatic answers in child workflow
            await self._process_automatic_answers(timestamp)
            
            # Notify observers
            if self.current_question:
                await self._notify_observers(
                    QuestionPathNextQuestionReady(current_question=self.current_question)
                )
    
    async def _complete_child_workflow(self, timestamp: int) -> None:
        """Complete child workflow and resume parent
        
        Args:
            timestamp: Current timestamp
        """
        if not self.level_stack:
            # No parent to resume, workflow complete
            self.current_question = None
            await self._notify_observers(
                QuestionPathCompleted(reason=QuestionPathCompletedReason.CLOSED)
            )
            return
        
        # Pop parent level from stack
        parent_level = self.level_stack.pop()
        
        # Merge child context modifications back to parent
        if self.current_level:
            self.planning_context.update(self.current_level.planning_context)
        
        # Restore parent level
        self.current_level = parent_level
        self.entries = parent_level.level_entries
        self.current_entry_index = parent_level.stopped_at_entry_index
        
        # Advance to next question in parent workflow
        await self._advance_to_next_question(timestamp)
    
    async def _advance_to_next_question(self, timestamp: int) -> None:
        """Advance to next question in current level
        
        Args:
            timestamp: Current timestamp
        """
        self.current_entry_index += 1
        
        if self.current_entry_index < len(self.entries):
            self.current_question = self.entries[self.current_entry_index]
            
            # Update current level tracking
            if self.current_level:
                self.current_level = QuestionPathLevelTracker(
                    stopped_at_entry=self.current_question,
                    stopped_at_entry_index=self.current_entry_index,
                    level_entries=self.current_level.level_entries,
                    planning_context=self.current_level.planning_context
                )
            
            # Process automatic answers
            await self._process_automatic_answers(timestamp)
            
            # Notify observers of next question requiring user input
            if self.current_question:
                await self._notify_observers(
                    QuestionPathNextQuestionReady(current_question=self.current_question)
                )
        else:
            # Current level complete, check if in child workflow
            if self.level_stack:
                await self._complete_child_workflow(timestamp)
            else:
                # Workflow complete
                self.current_question = None
                await self._notify_observers(
                    QuestionPathCompleted(reason=QuestionPathCompletedReason.CLOSED)
                )
    
    def get_feedback_array(self) -> List[QuestionPathFeedback]:
        """Get committed feedback history in order
        
        Returns:
            Ordered list of feedback records
        """
        # Return feedback sorted by ID (maintains insertion order)
        return [self.feedback_map[i] for i in sorted(self.feedback_map.keys())]
    
    def serialize(self) -> Dict[str, Any]:
        """Serialize traverser state to JSON-compatible dict
        
        Sensitive fields are stored as environment variable references.
        
        Returns:
            Dictionary containing complete traverser state
        """
        return {
            "workflow_version_hash": self.workflow_version_hash,
            "current_entry_index": self.current_entry_index,
            "current_feedback_id": self.current_feedback_id,
            "feedback_history": [fb.to_dict(redact_secrets=False) for fb in self.get_feedback_array()],
            "current_level": self.current_level.to_dict() if self.current_level else None,
            "level_stack": [level.to_dict() for level in self.level_stack],
            "planning_context": self.planning_context,
            "deferred_operations": self.deferred_operations_registry.serialize()
        }
    
    async def restore_async(
        self,
        state: Dict[str, Any],
        timestamp: int
    ) -> None:
        """Restore session from serialized state
        
        Args:
            state: Serialized state dictionary
            timestamp: Current timestamp for restoration
            
        Raises:
            ValueError: If state schema is invalid or version mismatch detected
        """
        # Validate schema
        self._validate_session_schema(state)
        
        # Check version hash
        if state.get("workflow_version_hash") != self.workflow_version_hash:
            raise ValueError(
                f"Workflow version mismatch: session uses {state.get('workflow_version_hash')}, "
                f"current is {self.workflow_version_hash}"
            )
        
        # Restore feedback history
        self.feedback_map.clear()
        feedbacks = [QuestionPathFeedback.from_dict(fb) for fb in state.get("feedback_history", [])]
        for feedback in feedbacks:
            self.feedback_map[feedback.feedback_id] = feedback
            if feedback.feedback_id >= self.current_feedback_id:
                self.current_feedback_id = feedback.feedback_id + 1
        
        # Restore position
        self.current_entry_index = state.get("current_entry_index", 0)
        
        # Restore level stack
        self.level_stack = [
            QuestionPathLevelTracker.from_dict(level) 
            for level in state.get("level_stack", [])
        ]
        
        # Restore current level
        if state.get("current_level"):
            self.current_level = QuestionPathLevelTracker.from_dict(state["current_level"])
        
        # Restore deferred operations
        self.deferred_operations_registry.restore(state.get("deferred_operations", []))
        
        # Restore planning context
        self.planning_context = state.get("planning_context", {})
        
        # Set current question
        if self.current_entry_index < len(self.entries):
            self.current_question = self.entries[self.current_entry_index]
        else:
            self.current_question = None
        
        # Notify observers of session restoration
        session_id = state.get("session_id", "unknown")
        await self._notify_observers(
            SessionRestored(session_id=session_id, feedback_count=len(feedbacks))
        )
    
    def _validate_session_schema(self, state: Dict[str, Any]) -> None:
        """Validate session state schema
        
        Args:
            state: State dictionary to validate
            
        Raises:
            ValueError: If schema is invalid
        """
        required_fields = ["workflow_version_hash", "current_entry_index", "current_feedback_id", "feedback_history"]
        for field in required_fields:
            if field not in state:
                raise ValueError(f"Invalid session schema: missing required field '{field}'")
    
    def build_platform_context(self) -> Dict[str, Any]:
        """Build PlatformContext from feedback history with resolved secrets
        
        Returns:
            Dictionary mapping question IDs to resolved answer values
        """
        from ..secrets import SecretResolver
        
        context = {}
        for feedback in self.get_feedback_array():
            # Store answer value (secrets already resolved during deserialization)
            context[feedback.entry.id] = feedback.entry_data.value
        
        return context
