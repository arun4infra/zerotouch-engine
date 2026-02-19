"""
Checkpoint 1: Core Traversal Validation

Integration test that validates QuestionPathTraverser with basic navigation,
feedback history, and level tracking.

Test creates a simple 3-question workflow, answers all questions, and verifies:
- Feedback history order and completeness
- Level tracking consistency
- Navigation state updates
"""
import pytest
import time
from workflow_engine.core.traverser import QuestionPathTraverser
from workflow_engine.models.entry import Entry, EntryData, EntryType


@pytest.mark.asyncio
async def test_core_traversal_basic_navigation():
    """Test basic navigation through 3-question workflow"""
    # Create simple 3-question workflow
    entries = [
        Entry(
            id="q1",
            type=EntryType.STRING,
            prompt="What is your name?",
            sensitive=False
        ),
        Entry(
            id="q2",
            type=EntryType.INTEGER,
            prompt="What is your age?",
            sensitive=False
        ),
        Entry(
            id="q3",
            type=EntryType.BOOLEAN,
            prompt="Do you agree?",
            sensitive=False
        )
    ]
    
    # Initialize traverser
    traverser = QuestionPathTraverser(entries=entries)
    
    # Start workflow
    timestamp = int(time.time() * 1000)
    await traverser.start_async(timestamp)
    
    # Verify first question
    current = traverser.get_current_question()
    assert current is not None
    assert current.id == "q1"
    assert current.prompt == "What is your name?"
    
    # Answer first question
    answer1 = EntryData(type=EntryType.STRING, value="Alice")
    await traverser.answer_current_question_async(answer1, timestamp + 1)
    
    # Verify second question
    current = traverser.get_current_question()
    assert current is not None
    assert current.id == "q2"
    assert current.prompt == "What is your age?"
    
    # Answer second question
    answer2 = EntryData(type=EntryType.INTEGER, value=30)
    await traverser.answer_current_question_async(answer2, timestamp + 2)
    
    # Verify third question
    current = traverser.get_current_question()
    assert current is not None
    assert current.id == "q3"
    assert current.prompt == "Do you agree?"
    
    # Answer third question
    answer3 = EntryData(type=EntryType.BOOLEAN, value=True)
    await traverser.answer_current_question_async(answer3, timestamp + 3)
    
    # Verify workflow complete
    current = traverser.get_current_question()
    assert current is None


@pytest.mark.asyncio
async def test_core_traversal_feedback_history():
    """Test feedback history order and completeness"""
    # Create 3-question workflow
    entries = [
        Entry(id="q1", type=EntryType.STRING, prompt="Name?", sensitive=False),
        Entry(id="q2", type=EntryType.INTEGER, prompt="Age?", sensitive=False),
        Entry(id="q3", type=EntryType.BOOLEAN, prompt="Agree?", sensitive=False)
    ]
    
    traverser = QuestionPathTraverser(entries=entries)
    timestamp = int(time.time() * 1000)
    await traverser.start_async(timestamp)
    
    # Answer all questions
    await traverser.answer_current_question_async(
        EntryData(type=EntryType.STRING, value="Bob"),
        timestamp + 1
    )
    await traverser.answer_current_question_async(
        EntryData(type=EntryType.INTEGER, value=25),
        timestamp + 2
    )
    await traverser.answer_current_question_async(
        EntryData(type=EntryType.BOOLEAN, value=False),
        timestamp + 3
    )
    
    # Get feedback history
    feedback_array = traverser.get_feedback_array()
    
    # Verify completeness
    assert len(feedback_array) == 3
    
    # Verify order (monotonic feedback IDs)
    assert feedback_array[0].feedback_id == 0
    assert feedback_array[1].feedback_id == 1
    assert feedback_array[2].feedback_id == 2
    
    # Verify timestamps are in order
    assert feedback_array[0].timestamp == timestamp + 1
    assert feedback_array[1].timestamp == timestamp + 2
    assert feedback_array[2].timestamp == timestamp + 3
    
    # Verify question context
    assert feedback_array[0].entry.id == "q1"
    assert feedback_array[1].entry.id == "q2"
    assert feedback_array[2].entry.id == "q3"
    
    # Verify answer values
    assert feedback_array[0].entry_data.value == "Bob"
    assert feedback_array[1].entry_data.value == 25
    assert feedback_array[2].entry_data.value == False
    
    # Verify immutability flags
    assert feedback_array[0].is_automatic == False
    assert feedback_array[0].is_sensitive == False


@pytest.mark.asyncio
async def test_core_traversal_level_tracking():
    """Test level tracking consistency during navigation"""
    # Create 3-question workflow
    entries = [
        Entry(id="q1", type=EntryType.STRING, prompt="Q1", sensitive=False),
        Entry(id="q2", type=EntryType.STRING, prompt="Q2", sensitive=False),
        Entry(id="q3", type=EntryType.STRING, prompt="Q3", sensitive=False)
    ]
    
    traverser = QuestionPathTraverser(entries=entries, planning_context={"test": "context"})
    timestamp = int(time.time() * 1000)
    await traverser.start_async(timestamp)
    
    # Verify initial level tracking
    assert traverser.current_level is not None
    assert traverser.current_level.stopped_at_entry.id == "q1"
    assert traverser.current_level.stopped_at_entry_index == 0
    assert len(traverser.current_level.level_entries) == 3
    assert traverser.current_level.planning_context == {"test": "context"}
    
    # Answer first question
    await traverser.answer_current_question_async(
        EntryData(type=EntryType.STRING, value="answer1"),
        timestamp + 1
    )
    
    # Verify level tracking updated
    assert traverser.current_level.stopped_at_entry.id == "q2"
    assert traverser.current_level.stopped_at_entry_index == 1
    
    # Answer second question
    await traverser.answer_current_question_async(
        EntryData(type=EntryType.STRING, value="answer2"),
        timestamp + 2
    )
    
    # Verify level tracking updated
    assert traverser.current_level.stopped_at_entry.id == "q3"
    assert traverser.current_level.stopped_at_entry_index == 2
    
    # Answer third question
    await traverser.answer_current_question_async(
        EntryData(type=EntryType.STRING, value="answer3"),
        timestamp + 3
    )
    
    # Verify workflow complete (current_question is None)
    assert traverser.get_current_question() is None


@pytest.mark.asyncio
async def test_core_traversal_empty_workflow():
    """Test edge case: empty workflow"""
    traverser = QuestionPathTraverser(entries=[])
    timestamp = int(time.time() * 1000)
    await traverser.start_async(timestamp)
    
    # Verify no current question
    assert traverser.get_current_question() is None
    
    # Verify empty feedback history
    assert len(traverser.get_feedback_array()) == 0


@pytest.mark.asyncio
async def test_core_traversal_single_question():
    """Test edge case: single question workflow"""
    entries = [
        Entry(id="only", type=EntryType.STRING, prompt="Only question?", sensitive=False)
    ]
    
    traverser = QuestionPathTraverser(entries=entries)
    timestamp = int(time.time() * 1000)
    await traverser.start_async(timestamp)
    
    # Verify first question
    assert traverser.get_current_question().id == "only"
    
    # Answer question
    await traverser.answer_current_question_async(
        EntryData(type=EntryType.STRING, value="answer"),
        timestamp + 1
    )
    
    # Verify workflow complete
    assert traverser.get_current_question() is None
    
    # Verify feedback recorded
    feedback = traverser.get_feedback_array()
    assert len(feedback) == 1
    assert feedback[0].entry.id == "only"
    assert feedback[0].entry_data.value == "answer"


@pytest.mark.asyncio
async def test_core_traversal_sensitive_field():
    """Test sensitive field handling in feedback"""
    entries = [
        Entry(
            id="password",
            type=EntryType.STRING,
            prompt="Enter password",
            sensitive=True,
            env_var_name="MY_PASSWORD"
        )
    ]
    
    traverser = QuestionPathTraverser(entries=entries)
    timestamp = int(time.time() * 1000)
    await traverser.start_async(timestamp)
    
    # Answer sensitive question
    await traverser.answer_current_question_async(
        EntryData(type=EntryType.STRING, value="secret123"),
        timestamp + 1
    )
    
    # Verify feedback marked as sensitive
    feedback = traverser.get_feedback_array()
    assert len(feedback) == 1
    assert feedback[0].is_sensitive == True
    assert feedback[0].entry.sensitive == True
    assert feedback[0].entry.env_var_name == "MY_PASSWORD"
