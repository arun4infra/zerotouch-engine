"""Checkpoint 3: DSL Validation and Answer Validation

Tests workflow DSL parser, validation rules, and observer notifications.
"""
import pytest
from pathlib import Path
from workflow_engine.parser.dsl_parser import WorkflowDSLParser
from workflow_engine.validation import AnswerValidator
from workflow_engine.models.entry import EntryData, EntryType, Entry
from workflow_engine.models.workflow_dsl import QuestionNode, ValidationRules
from workflow_engine.core.traverser import QuestionPathTraverser
from workflow_engine.core.observer import (
    QuestionPathTraverserObserver,
    QuestionPathNextQuestionReady,
    QuestionPathFeedbackEntered,
    QuestionPathCompleted
)


def question_node_to_entry(node: QuestionNode) -> Entry:
    """Convert QuestionNode to Entry for traverser"""
    return Entry(
        id=node.id,
        type=EntryType(node.type),
        prompt=node.prompt,
        help_text=node.help_text,
        default=node.default,
        automatic_answer=node.automatic_answer,
        sensitive=node.sensitive
    )


class TestObserver(QuestionPathTraverserObserver):
    """Test observer to capture notifications"""
    def __init__(self):
        self.notifications = []
    
    async def receive_notification_async(self, notification):
        self.notifications.append(notification)


@pytest.mark.asyncio
async def test_dsl_parser_valid_workflow(tmp_path):
    """Test parsing valid workflow YAML"""
    workflow_yaml = tmp_path / "workflow.yaml"
    workflow_yaml.write_text("""
version: "1.0.0"
workflow_id: test-workflow
states:
  q1:
    question:
      id: q1
      type: string
      prompt: "Enter name"
    next_state: q2
  q2:
    question:
      id: q2
      type: integer
      prompt: "Enter age"
    next_state: null
transitions:
  - from_state: q1
    to_state: q2
""")
    
    parser = WorkflowDSLParser()
    workflow = await parser.parse_yaml(workflow_yaml)
    
    assert workflow.workflow_id == "test-workflow"
    assert len(workflow.states) == 2
    assert "q1" in workflow.states
    assert "q2" in workflow.states


@pytest.mark.asyncio
async def test_dsl_parser_invalid_workflow():
    """Test parsing invalid workflow YAML"""
    parser = WorkflowDSLParser()
    
    with pytest.raises(Exception):  # Should raise validation error
        await parser.parse_yaml(Path("nonexistent.yaml"))


@pytest.mark.asyncio
async def test_validation_regex():
    """Test regex validation for string answers"""
    validator = AnswerValidator()
    
    question = QuestionNode(
        id="email",
        type="string",
        prompt="Enter email",
        validation=ValidationRules(regex=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    )
    
    # Valid email
    valid_data = EntryData(type=EntryType.STRING, value="test@example.com")
    assert validator.validate(valid_data, question) is True
    
    # Invalid email
    invalid_data = EntryData(type=EntryType.STRING, value="not-an-email")
    assert validator.validate(invalid_data, question) is False


@pytest.mark.asyncio
async def test_validation_range():
    """Test range validation for integer answers"""
    validator = AnswerValidator()
    
    question = QuestionNode(
        id="age",
        type="integer",
        prompt="Enter age",
        validation=ValidationRules(min_value=0, max_value=120)
    )
    
    # Valid age
    valid_data = EntryData(type=EntryType.INTEGER, value=25)
    assert validator.validate(valid_data, question) is True
    
    # Invalid age (too high)
    invalid_data = EntryData(type=EntryType.INTEGER, value=150)
    assert validator.validate(invalid_data, question) is False


@pytest.mark.asyncio
async def test_validation_enum():
    """Test enum validation for choice answers"""
    validator = AnswerValidator()
    
    question = QuestionNode(
        id="color",
        type="choice",
        prompt="Choose color",
        validation=ValidationRules(choices=["red", "green", "blue"])
    )
    
    # Valid choice
    valid_data = EntryData(type=EntryType.CHOICE, value="red")
    assert validator.validate(valid_data, question) is True
    
    # Invalid choice
    invalid_data = EntryData(type=EntryType.CHOICE, value="yellow")
    assert validator.validate(invalid_data, question) is False


@pytest.mark.asyncio
async def test_observer_notifications(tmp_path):
    """Test observer receives all state change notifications"""
    workflow_yaml = tmp_path / "workflow.yaml"
    workflow_yaml.write_text("""
version: "1.0.0"
workflow_id: test-workflow
states:
  q1:
    question:
      id: q1
      type: string
      prompt: "Question 1"
    next_state: null
transitions: []
""")
    
    parser = WorkflowDSLParser()
    workflow = await parser.parse_yaml(workflow_yaml)
    
    # Convert workflow to entries list
    entries = [question_node_to_entry(state.question) for state in workflow.states.values()]
    
    observer = TestObserver()
    traverser = QuestionPathTraverser(entries)
    traverser.register_observer(observer)
    
    # Start workflow
    await traverser.start_async(1000)
    
    # Should emit QuestionPathNextQuestionReady
    assert len(observer.notifications) >= 1
    assert isinstance(observer.notifications[0], QuestionPathNextQuestionReady)
    
    # Answer question
    answer = EntryData(type=EntryType.STRING, value="answer1")
    await traverser.answer_current_question_async(answer, 2000)
    
    # Should emit QuestionPathFeedbackEntered and QuestionPathCompleted
    assert any(isinstance(n, QuestionPathFeedbackEntered) for n in observer.notifications)
    assert any(isinstance(n, QuestionPathCompleted) for n in observer.notifications)


@pytest.mark.asyncio
async def test_conditional_branching(tmp_path):
    """Test conditional transitions based on answers"""
    workflow_yaml = tmp_path / "workflow.yaml"
    workflow_yaml.write_text("""
version: "1.0.0"
workflow_id: conditional-workflow
states:
  q1:
    question:
      id: q1
      type: boolean
      prompt: "Enable feature?"
    next_state: q2
  q2:
    question:
      id: q2
      type: string
      prompt: "Feature name"
      automatic_answer: "${q1}"
    next_state: null
transitions:
  - from_state: q1
    to_state: q2
    condition: "${q1} == true"
""")
    
    parser = WorkflowDSLParser()
    workflow = await parser.parse_yaml(workflow_yaml)
    
    assert len(workflow.transitions) == 1
    assert workflow.transitions[0].condition is not None


@pytest.mark.asyncio
async def test_automatic_answer_expression(tmp_path):
    """Test automatic answer with expression evaluation"""
    workflow_yaml = tmp_path / "workflow.yaml"
    workflow_yaml.write_text("""
version: "1.0.0"
workflow_id: auto-answer-workflow
states:
  q1:
    question:
      id: q1
      type: string
      prompt: "Enter name"
    next_state: q2
  q2:
    question:
      id: q2
      type: string
      prompt: "Confirm name"
      automatic_answer: "${q1}"
    next_state: null
transitions:
  - from_state: q1
    to_state: q2
""")
    
    parser = WorkflowDSLParser()
    workflow = await parser.parse_yaml(workflow_yaml)
    
    assert workflow.states["q2"].question.automatic_answer == "${q1}"
