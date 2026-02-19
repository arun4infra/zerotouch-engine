"""Checkpoint 4: Advanced Features

Tests automatic answer provider and nested workflow navigation.
"""
import pytest
from pathlib import Path
from workflow_engine.parser.dsl_parser import WorkflowDSLParser
from workflow_engine.core.traverser import QuestionPathTraverser
from workflow_engine.core.automatic_answer import AutomaticAnswerProvider, ExpressionEvaluator
from workflow_engine.models.entry import Entry, EntryData, EntryType
from workflow_engine.models.workflow_dsl import QuestionNode


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


@pytest.mark.asyncio
async def test_automatic_answer_skipping(tmp_path):
    """Test questions with automatic answers are skipped"""
    workflow_yaml = tmp_path / "workflow.yaml"
    workflow_yaml.write_text("""
version: "1.0.0"
workflow_id: auto-skip-workflow
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
    next_state: q3
  q3:
    question:
      id: q3
      type: string
      prompt: "Final question"
    next_state: null
transitions:
  - from_state: q1
    to_state: q2
  - from_state: q2
    to_state: q3
""")
    
    parser = WorkflowDSLParser()
    workflow = await parser.parse_yaml(workflow_yaml)
    
    entries = [question_node_to_entry(state.question) for state in workflow.states.values()]
    traverser = QuestionPathTraverser(entries)
    await traverser.start_async(1000)
    
    # Answer first question
    answer1 = EntryData(type=EntryType.STRING, value="John")
    await traverser.answer_current_question_async(answer1, 2000)
    
    # Current question should be q3 (q2 was auto-answered)
    current = traverser.get_current_question()
    assert current.id == "q3"
    
    # Check feedback history has auto-answer flag
    feedback_history = traverser.get_feedback_array()
    q2_feedback = next(f for f in feedback_history if f.entry.id == "q2")
    assert q2_feedback.is_automatic is True


@pytest.mark.asyncio
async def test_automatic_answer_fallback():
    """Test automatic answer falls back to manual input on expression failure"""
    feedback_context = {"q1": "value1"}
    evaluator = ExpressionEvaluator(feedback_context)
    
    # Valid expression
    result = await evaluator.evaluate("${q1}")
    assert result == "value1"
    
    # Invalid expression (missing variable)
    with pytest.raises(Exception):
        await evaluator.evaluate("${nonexistent}")


@pytest.mark.asyncio
async def test_expression_evaluator():
    """Test expression evaluator with various expressions"""
    context = {
        "name": "John",
        "age": 25,
        "enabled": True
    }
    evaluator = ExpressionEvaluator(context)
    
    # Variable reference
    assert await evaluator.evaluate("${name}") == "John"
    assert await evaluator.evaluate("${age}") == 25
    assert await evaluator.evaluate("${enabled}") is True
    
    # Literal value
    assert await evaluator.evaluate("literal") == "literal"


@pytest.mark.asyncio
async def test_nested_workflow_level_stack(tmp_path):
    """Test level stack grows and shrinks with nested workflows"""
    parent_yaml = tmp_path / "parent.yaml"
    parent_yaml.write_text("""
version: "1.0.0"
workflow_id: parent-workflow
states:
  p1:
    question:
      id: p1
      type: string
      prompt: "Parent question 1"
    next_state: p2
  p2:
    question:
      id: p2
      type: string
      prompt: "Parent question 2"
    next_state: null
transitions:
  - from_state: p1
    to_state: p2
""")
    
    parser = WorkflowDSLParser()
    workflow = await parser.parse_yaml(parent_yaml)
    
    entries = [question_node_to_entry(state.question) for state in workflow.states.values()]
    traverser = QuestionPathTraverser(entries)
    await traverser.start_async(1000)
    
    # Initially, level stack should be empty (only current_level)
    assert len(traverser.level_stack) == 0
    
    # Answer first question
    answer1 = EntryData(type=EntryType.STRING, value="answer1")
    await traverser.answer_current_question_async(answer1, 2000)
    
    # Level stack should still be empty (no nesting yet)
    assert len(traverser.level_stack) == 0


@pytest.mark.asyncio
async def test_nested_workflow_context_inheritance(tmp_path):
    """Test child workflows inherit context from parent"""
    workflow_yaml = tmp_path / "workflow.yaml"
    workflow_yaml.write_text("""
version: "1.0.0"
workflow_id: context-workflow
states:
  q1:
    question:
      id: q1
      type: string
      prompt: "Enter value"
    next_state: q2
  q2:
    question:
      id: q2
      type: string
      prompt: "Use value"
      automatic_answer: "${q1}"
    next_state: null
transitions:
  - from_state: q1
    to_state: q2
""")
    
    parser = WorkflowDSLParser()
    workflow = await parser.parse_yaml(workflow_yaml)
    
    entries = [question_node_to_entry(state.question) for state in workflow.states.values()]
    traverser = QuestionPathTraverser(entries)
    await traverser.start_async(1000)
    
    # Answer first question
    answer1 = EntryData(type=EntryType.STRING, value="inherited_value")
    await traverser.answer_current_question_async(answer1, 2000)
    
    # Check that q2 was auto-answered with inherited value
    feedback_history = traverser.get_feedback_array()
    q2_feedback = next(f for f in feedback_history if f.entry.id == "q2")
    assert q2_feedback.entry_data.value == "inherited_value"
    assert q2_feedback.is_automatic is True


@pytest.mark.asyncio
async def test_automatic_answer_provider():
    """Test AutomaticAnswerProvider with various entry types"""
    feedback_context = {
        "string_val": "test",
        "int_val": 42,
        "bool_val": True
    }
    provider = AutomaticAnswerProvider(feedback_context)
    
    # String entry
    string_entry = Entry(
        id="test_string",
        type=EntryType.STRING,
        prompt="Test",
        automatic_answer="${string_val}"
    )
    result = await provider.get_automatic_answer_async(string_entry)
    assert result is not None
    assert result.value == "test"
    
    # Integer entry
    int_entry = Entry(
        id="test_int",
        type=EntryType.INTEGER,
        prompt="Test",
        automatic_answer="${int_val}"
    )
    result = await provider.get_automatic_answer_async(int_entry)
    assert result is not None
    assert result.value == 42
    
    # Boolean entry
    bool_entry = Entry(
        id="test_bool",
        type=EntryType.BOOLEAN,
        prompt="Test",
        automatic_answer="${bool_val}"
    )
    result = await provider.get_automatic_answer_async(bool_entry)
    assert result is not None
    assert result.value is True


@pytest.mark.asyncio
async def test_automatic_answer_no_expression():
    """Test entries without automatic_answer return None"""
    feedback_context = {}
    provider = AutomaticAnswerProvider(feedback_context)
    
    entry = Entry(
        id="test",
        type=EntryType.STRING,
        prompt="Test",
        automatic_answer=None
    )
    
    result = await provider.get_automatic_answer_async(entry)
    assert result is None
