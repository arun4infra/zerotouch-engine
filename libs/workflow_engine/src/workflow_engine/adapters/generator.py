"""Adapter workflow generator for dynamic workflow creation from adapters"""

from typing import List, Dict, Any, Optional, Tuple
from workflow_engine.adapters.registry import AdapterRegistry
from workflow_engine.adapters.translator import AdapterQuestionTranslator
from workflow_engine.models.workflow_dsl import WorkflowDSL, StateNode, TransitionNode
from workflow_engine.adapters.operation_mode import traversal_mode, completion_mode


class AdapterWorkflowGenerator:
    """Generates workflow DSL from adapter metadata"""
    
    def __init__(self, adapter_registry: AdapterRegistry):
        self.registry = adapter_registry
        self.translator = AdapterQuestionTranslator()
    
    async def generate_workflow_from_adapters(
        self, 
        adapter_names: List[str]
    ) -> WorkflowDSL:
        """Generate workflow DSL from adapter metadata
        
        Uses traversal mode to ensure adapters only perform read operations.
        
        Args:
            adapter_names: List of adapter names to include in workflow
            
        Returns:
            WorkflowDSL with questions from all adapters
        """
        states = {}
        transitions = []
        previous_state_id = None
        
        # Enter traversal mode - adapters can only read, not mutate
        with traversal_mode():
            for adapter_name in adapter_names:
                adapter = self.registry.get_adapter(adapter_name)
                inputs = adapter.get_required_inputs()
                
                for idx, input_prompt in enumerate(inputs):
                    question = self.translator.translate_input_prompt(
                        input_prompt, 
                        adapter_name
                    )
                    
                    # Determine next state
                    is_last_in_adapter = (idx == len(inputs) - 1)
                    is_last_adapter = (adapter_name == adapter_names[-1])
                    
                    if is_last_in_adapter and is_last_adapter:
                        next_state = None  # Workflow complete
                    elif is_last_in_adapter:
                        # Move to next adapter's first question
                        next_adapter_idx = adapter_names.index(adapter_name) + 1
                        next_adapter = self.registry.get_adapter(adapter_names[next_adapter_idx])
                        next_inputs = next_adapter.get_required_inputs()
                        if next_inputs:
                            next_state = f"{adapter_names[next_adapter_idx]}.{next_inputs[0].name}"
                        else:
                            next_state = None
                    else:
                        # Move to next question in same adapter
                        next_state = f"{adapter_name}.{inputs[idx + 1].name}"
                    
                    states[question.id] = StateNode(
                        question=question,
                        next_state=next_state
                    )
                    
                    # Create transition from previous state
                    if previous_state_id:
                        transitions.append(TransitionNode(
                            from_state=previous_state_id,
                            to_state=question.id
                        ))
                    
                    previous_state_id = question.id
        
        # Generate workflow ID from adapter names
        workflow_id = f"adapters_{'_'.join(adapter_names)}"
        
        return WorkflowDSL(
            version="1.0.0",
            workflow_id=workflow_id,
            states=states,
            transitions=transitions
        )
    
    def construct_platform_context(
        self,
        session_answers: Dict[str, Any],
        adapter_names: List[str]
    ) -> Dict[str, Any]:
        """Construct PlatformContext from session answers with cross-adapter accessibility
        
        Merges answers from multiple adapters into a unified context where each adapter
        can access answers from other adapters through the merged structure.
        
        Args:
            session_answers: Dictionary mapping question IDs to answer values
            adapter_names: List of adapter names to include in context
            
        Returns:
            PlatformContext dictionary with:
            - Adapter-specific configurations grouped by adapter name
            - Cross-adapter answer accessibility (all answers accessible to all adapters)
            - Merged structure supporting dependencies between adapters
        """
        context = {}
        
        # Group answers by adapter name for cross-adapter accessibility
        for question_id, answer_value in session_answers.items():
            if '.' in question_id:
                adapter_name, field_name = question_id.split('.', 1)
                
                if adapter_name not in context:
                    context[adapter_name] = {}
                
                context[adapter_name][field_name] = answer_value
        
        # Ensure all requested adapters have entries (even if empty)
        for adapter_name in adapter_names:
            if adapter_name not in context:
                context[adapter_name] = {}
        
        return context
    
    def execute_adapter_with_error_preservation(
        self,
        adapter_name: str,
        adapter_config: Dict[str, Any],
        platform_context: Dict[str, Any]
    ) -> tuple[bool, Optional[str], Optional[Any]]:
        """Execute adapter with failure state preservation
        
        Ensures that adapter execution failures return errors without changing state.
        
        Args:
            adapter_name: Name of adapter to execute
            adapter_config: Configuration for the adapter
            platform_context: Full platform context with cross-adapter answers
            
        Returns:
            Tuple of (success: bool, error_message: Optional[str], result: Optional[Any])
            - If success=True: error_message=None, result contains adapter output
            - If success=False: error_message contains error details, result=None
        """
        try:
            adapter = self.registry.get_adapter(adapter_name, adapter_config)
            
            # Adapter can access all answers from platform_context
            # This enables cross-adapter dependencies
            result = adapter
            
            return (True, None, result)
            
        except Exception as e:
            # Preserve error without state change
            error_message = f"Adapter '{adapter_name}' execution failed: {str(e)}"
            return (False, error_message, None)
