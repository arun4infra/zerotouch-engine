"""
Checkpoint 2: Session Persistence Validation

Integration test that validates complete session serialization, FilesystemStore
with atomic writes, and session restoration.

Test starts workflow, answers 2 questions, saves to filesystem, simulates process
kill by creating new traverser instance, restores from filesystem, and verifies
state matches.
"""
import pytest
import time
import uuid
from pathlib import Path
import tempfile
import shutil
from workflow_engine.core.traverser import QuestionPathTraverser
from workflow_engine.models.entry import Entry, EntryData, EntryType
from workflow_engine.storage.session_store import FilesystemStore


@pytest.mark.asyncio
async def test_session_persistence_full_cycle():
    """Test complete session persistence cycle with filesystem storage"""
    # Create temporary directory for test
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # Create 3-question workflow
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
        
        # Initialize traverser and filesystem store
        traverser = QuestionPathTraverser(entries=entries, planning_context={"test": "context"})
        store = FilesystemStore(base_path=temp_dir)
        session_id = str(uuid.uuid4())
        
        # Start workflow
        timestamp = int(time.time() * 1000)
        await traverser.start_async(timestamp)
        
        # Answer first question
        assert traverser.get_current_question().id == "q1"
        await traverser.answer_current_question_async(
            EntryData(type=EntryType.STRING, value="Alice"),
            timestamp + 1
        )
        
        # Answer second question
        assert traverser.get_current_question().id == "q2"
        await traverser.answer_current_question_async(
            EntryData(type=EntryType.INTEGER, value=30),
            timestamp + 2
        )
        
        # Verify we're at third question
        assert traverser.get_current_question().id == "q3"
        
        # Serialize and save to filesystem
        state = traverser.serialize()
        await store.save(session_id, state)
        
        # Verify file was created
        session_file = temp_dir / "session.json"
        assert session_file.exists()
        
        # Simulate process kill: create new traverser instance
        new_traverser = QuestionPathTraverser(entries=entries, planning_context={"test": "context"})
        
        # Load state from filesystem
        loaded_state = await store.load(session_id)
        assert loaded_state is not None
        
        # Restore session
        await new_traverser.restore_async(loaded_state, timestamp + 3)
        
        # Verify state matches
        assert new_traverser.get_current_question().id == "q3"
        assert new_traverser.current_entry_index == 2
        
        # Verify feedback history restored
        feedback = new_traverser.get_feedback_array()
        assert len(feedback) == 2
        assert feedback[0].entry.id == "q1"
        assert feedback[0].entry_data.value == "Alice"
        assert feedback[1].entry.id == "q2"
        assert feedback[1].entry_data.value == 30
        
        # Verify level tracking restored
        assert new_traverser.current_level is not None
        assert new_traverser.current_level.stopped_at_entry.id == "q3"
        assert new_traverser.current_level.stopped_at_entry_index == 2
        assert new_traverser.current_level.planning_context == {"test": "context"}
        
        # Continue workflow with restored session
        await new_traverser.answer_current_question_async(
            EntryData(type=EntryType.BOOLEAN, value=True),
            timestamp + 4
        )
        
        # Verify workflow complete
        assert new_traverser.get_current_question() is None
        
        # Verify all feedback recorded
        final_feedback = new_traverser.get_feedback_array()
        assert len(final_feedback) == 3
        assert final_feedback[2].entry.id == "q3"
        assert final_feedback[2].entry_data.value == True
        
    finally:
        # Cleanup temp directory
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_filesystem_atomic_write():
    """Test atomic write safety of FilesystemStore"""
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        store = FilesystemStore(base_path=temp_dir)
        session_id = str(uuid.uuid4())
        
        # Save initial state
        state1 = {
            "workflow_version_hash": "hash1",
            "current_entry_index": 0,
            "current_feedback_id": 0,
            "feedback_history": []
        }
        await store.save(session_id, state1)
        
        # Verify file exists
        session_file = temp_dir / "session.json"
        assert session_file.exists()
        
        # Save updated state (should atomically replace)
        state2 = {
            "workflow_version_hash": "hash1",
            "current_entry_index": 1,
            "current_feedback_id": 1,
            "feedback_history": [{"feedback_id": 0}]
        }
        await store.save(session_id, state2)
        
        # Load and verify we got the updated state
        loaded = await store.load(session_id)
        assert loaded is not None
        assert loaded["current_entry_index"] == 1
        assert loaded["current_feedback_id"] == 1
        assert len(loaded["feedback_history"]) == 1
        
        # Verify no temp file left behind
        temp_file = temp_dir / "session.json.tmp"
        assert not temp_file.exists()
        
    finally:
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_session_serialization_completeness():
    """Test that serialization includes all required fields"""
    entries = [
        Entry(id="q1", type=EntryType.STRING, prompt="Q1", sensitive=False),
        Entry(id="q2", type=EntryType.INTEGER, prompt="Q2", sensitive=False)
    ]
    
    traverser = QuestionPathTraverser(
        entries=entries,
        planning_context={"key": "value"}
    )
    
    timestamp = int(time.time() * 1000)
    await traverser.start_async(timestamp)
    
    # Answer first question
    await traverser.answer_current_question_async(
        EntryData(type=EntryType.STRING, value="answer1"),
        timestamp + 1
    )
    
    # Serialize
    state = traverser.serialize()
    
    # Verify all required fields present
    assert "workflow_version_hash" in state
    assert "current_entry_index" in state
    assert "current_feedback_id" in state
    assert "feedback_history" in state
    assert "current_level" in state
    assert "level_stack" in state
    assert "planning_context" in state
    assert "deferred_operations" in state
    
    # Verify field values
    assert state["current_entry_index"] == 1
    assert state["current_feedback_id"] == 1
    assert len(state["feedback_history"]) == 1
    assert state["planning_context"] == {"key": "value"}
    assert state["current_level"] is not None
    assert state["level_stack"] == []
    assert state["deferred_operations"] == []


@pytest.mark.asyncio
async def test_session_restoration_version_mismatch():
    """Test that version mismatch is detected during restoration"""
    entries = [
        Entry(id="q1", type=EntryType.STRING, prompt="Q1", sensitive=False)
    ]
    
    traverser = QuestionPathTraverser(entries=entries)
    timestamp = int(time.time() * 1000)
    await traverser.start_async(timestamp)
    
    # Serialize state
    state = traverser.serialize()
    
    # Modify workflow (different hash)
    modified_entries = [
        Entry(id="q1", type=EntryType.INTEGER, prompt="Q1 Modified", sensitive=False)
    ]
    new_traverser = QuestionPathTraverser(entries=modified_entries)
    
    # Attempt to restore with mismatched version
    with pytest.raises(ValueError, match="Workflow version mismatch"):
        await new_traverser.restore_async(state, timestamp + 1)


@pytest.mark.asyncio
async def test_session_restoration_invalid_schema():
    """Test that invalid schema is rejected during restoration"""
    entries = [
        Entry(id="q1", type=EntryType.STRING, prompt="Q1", sensitive=False)
    ]
    
    traverser = QuestionPathTraverser(entries=entries)
    timestamp = int(time.time() * 1000)
    
    # Invalid state missing required fields
    invalid_state = {
        "workflow_version_hash": "hash",
        # Missing current_entry_index, current_feedback_id, feedback_history
    }
    
    with pytest.raises(ValueError, match="Invalid session schema"):
        await traverser.restore_async(invalid_state, timestamp)


@pytest.mark.asyncio
async def test_filesystem_store_nonexistent_session():
    """Test loading nonexistent session returns None"""
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        store = FilesystemStore(base_path=temp_dir)
        
        # Load nonexistent session
        result = await store.load("nonexistent-session-id")
        assert result is None
        
    finally:
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_filesystem_store_delete():
    """Test session deletion"""
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        store = FilesystemStore(base_path=temp_dir)
        session_id = str(uuid.uuid4())
        
        # Save session
        state = {
            "workflow_version_hash": "hash",
            "current_entry_index": 0,
            "current_feedback_id": 0,
            "feedback_history": []
        }
        await store.save(session_id, state)
        
        # Verify file exists
        session_file = temp_dir / "session.json"
        assert session_file.exists()
        
        # Delete session
        await store.delete(session_id)
        
        # Verify file deleted
        assert not session_file.exists()
        
        # Load should return None
        result = await store.load(session_id)
        assert result is None
        
    finally:
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_sensitive_field_persistence():
    """Test that sensitive fields are properly persisted and restored"""
    import os
    temp_dir = Path(tempfile.mkdtemp())
    
    # Set environment variable for test
    os.environ["MY_PASSWORD"] = "secret123"
    
    try:
        entries = [
            Entry(
                id="password",
                type=EntryType.STRING,
                prompt="Enter password",
                sensitive=True,
                env_var_name="MY_PASSWORD"
            ),
            Entry(
                id="username",
                type=EntryType.STRING,
                prompt="Enter username",
                sensitive=False
            )
        ]
        
        traverser = QuestionPathTraverser(entries=entries)
        store = FilesystemStore(base_path=temp_dir)
        session_id = str(uuid.uuid4())
        
        timestamp = int(time.time() * 1000)
        await traverser.start_async(timestamp)
        
        # Answer sensitive question
        await traverser.answer_current_question_async(
            EntryData(type=EntryType.STRING, value="secret123"),
            timestamp + 1
        )
        
        # Serialize and save
        state = traverser.serialize()
        await store.save(session_id, state)
        
        # Create new traverser and restore
        new_traverser = QuestionPathTraverser(entries=entries)
        loaded_state = await store.load(session_id)
        await new_traverser.restore_async(loaded_state, timestamp + 2)
        
        # Verify sensitive feedback restored
        feedback = new_traverser.get_feedback_array()
        assert len(feedback) == 1
        assert feedback[0].is_sensitive == True
        assert feedback[0].entry.sensitive == True
        assert feedback[0].entry.env_var_name == "MY_PASSWORD"
        assert feedback[0].entry_data.value == "secret123"
        
    finally:
        # Clean up environment variable
        if "MY_PASSWORD" in os.environ:
            del os.environ["MY_PASSWORD"]
        shutil.rmtree(temp_dir)
