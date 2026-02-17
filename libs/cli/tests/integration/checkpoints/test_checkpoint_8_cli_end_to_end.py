"""Checkpoint 8: CLI Client and Error Handling

Tests complete CLI client with workflow commands, FilesystemStore integration,
and comprehensive error handling.
"""
import pytest
import asyncio
from pathlib import Path
import json

from libs.cli.workflow_commands import _start_workflow, _submit_answer, _restore_session, _restart_workflow
from libs.cli.storage import FilesystemStore


@pytest.mark.asyncio
async def test_cli_start_workflow(tmp_path):
    """Test CLI start command creates session and displays first question"""
    # Create test workflow
    workflow_yaml = tmp_path / "test.yaml"
    workflow_yaml.write_text("""
version: "1.0.0"
workflow_id: test-workflow
states:
  q1:
    question:
      id: q1
      type: string
      prompt: "Enter name"
    next_state: null
transitions: []
""")
    
    # Change to tmp directory for session storage
    import os
    original_dir = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        # Start workflow
        await _start_workflow("test-workflow", "test.yaml")
        
        # Verify session file created
        session_file = Path(".ztc/session.json")
        assert session_file.exists()
        
        # Verify session content
        with open(session_file) as f:
            sessions = json.load(f)
        
        assert len(sessions) == 1
        session_id = list(sessions.keys())[0]
        session = sessions[session_id]
        
        assert session["workflow_id"] == "test-workflow"
        assert "state_blob" in session
        
    finally:
        os.chdir(original_dir)


@pytest.mark.asyncio
async def test_cli_submit_answer(tmp_path):
    """Test CLI answer command submits answer and advances workflow"""
    # Create test workflow with 2 questions
    workflow_yaml = tmp_path / "test.yaml"
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
    
    import os
    original_dir = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        # Start workflow
        await _start_workflow("test-workflow", "test.yaml")
        
        # Get session ID
        with open(".ztc/session.json") as f:
            sessions = json.load(f)
        session_id = list(sessions.keys())[0]
        
        # Submit first answer
        await _submit_answer(session_id, "John")
        
        # Verify session updated
        with open(".ztc/session.json") as f:
            sessions = json.load(f)
        
        assert session_id in sessions
        
        # Submit second answer
        await _submit_answer(session_id, "25")
        
        # Verify session deleted after completion
        with open(".ztc/session.json") as f:
            sessions = json.load(f)
        
        assert session_id not in sessions
        
    finally:
        os.chdir(original_dir)


@pytest.mark.asyncio
async def test_cli_restore_session(tmp_path):
    """Test CLI restore command restores session state"""
    # Create test workflow
    workflow_yaml = tmp_path / "test.yaml"
    workflow_yaml.write_text("""
version: "1.0.0"
workflow_id: test-workflow
states:
  q1:
    question:
      id: q1
      type: string
      prompt: "Enter name"
    next_state: null
transitions: []
""")
    
    import os
    original_dir = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        # Start workflow
        await _start_workflow("test-workflow", "test.yaml")
        
        # Get session ID
        with open(".ztc/session.json") as f:
            sessions = json.load(f)
        session_id = list(sessions.keys())[0]
        
        # Restore session
        await _restore_session(session_id)
        
        # Verify session still exists
        with open(".ztc/session.json") as f:
            sessions = json.load(f)
        
        assert session_id in sessions
        
    finally:
        os.chdir(original_dir)


@pytest.mark.asyncio
async def test_cli_restart_workflow(tmp_path):
    """Test CLI restart command creates new session"""
    # Create test workflow
    workflow_yaml = tmp_path / "test.yaml"
    workflow_yaml.write_text("""
version: "1.0.0"
workflow_id: test-workflow
states:
  q1:
    question:
      id: q1
      type: string
      prompt: "Enter name"
    next_state: null
transitions: []
""")
    
    import os
    original_dir = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        # Start workflow
        await _start_workflow("test-workflow", "test.yaml")
        
        # Get first session ID
        with open(".ztc/session.json") as f:
            sessions = json.load(f)
        first_session_id = list(sessions.keys())[0]
        
        # Restart workflow
        await _restart_workflow("test-workflow", "test.yaml")
        
        # Get second session ID
        with open(".ztc/session.json") as f:
            sessions = json.load(f)
        
        # Should have 2 sessions now
        assert len(sessions) == 2
        
        # Verify new session ID is different
        session_ids = list(sessions.keys())
        assert first_session_id in session_ids
        second_session_id = [sid for sid in session_ids if sid != first_session_id][0]
        assert second_session_id != first_session_id
        
    finally:
        os.chdir(original_dir)


@pytest.mark.asyncio
async def test_filesystem_store_atomic_writes(tmp_path):
    """Test FilesystemStore performs atomic writes"""
    store = FilesystemStore(base_path=tmp_path / ".ztc")
    
    # Save multiple sessions
    await store.save("session1", {"data": "value1"})
    await store.save("session2", {"data": "value2"})
    
    # Verify both sessions exist
    session1 = await store.load("session1")
    session2 = await store.load("session2")
    
    assert session1["data"] == "value1"
    assert session2["data"] == "value2"
    
    # Verify no temp files left behind
    temp_files = list((tmp_path / ".ztc").glob("*.tmp"))
    assert len(temp_files) == 0


@pytest.mark.asyncio
async def test_filesystem_store_delete(tmp_path):
    """Test FilesystemStore deletes sessions"""
    store = FilesystemStore(base_path=tmp_path / ".ztc")
    
    # Save session
    await store.save("session1", {"data": "value1"})
    
    # Verify exists
    session = await store.load("session1")
    assert session is not None
    
    # Delete session
    await store.delete("session1")
    
    # Verify deleted
    session = await store.load("session1")
    assert session is None


@pytest.mark.asyncio
async def test_cli_error_handling_invalid_session(tmp_path):
    """Test CLI handles invalid session ID gracefully"""
    import os
    from click.exceptions import Exit
    original_dir = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        # Try to submit answer with invalid session ID
        with pytest.raises(Exit):
            await _submit_answer("invalid-session-id", "answer")
        
    finally:
        os.chdir(original_dir)


@pytest.mark.asyncio
async def test_cli_error_handling_missing_workflow(tmp_path):
    """Test CLI handles missing workflow file gracefully"""
    import os
    from click.exceptions import Exit
    original_dir = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        # Try to start workflow with missing file
        with pytest.raises(Exit):
            await _start_workflow("test-workflow", "nonexistent.yaml")
        
    finally:
        os.chdir(original_dir)


@pytest.mark.asyncio
async def test_cli_complete_workflow_lifecycle(tmp_path):
    """Test complete workflow lifecycle: start -> answer -> complete"""
    # Create test workflow
    workflow_yaml = tmp_path / "test.yaml"
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
    
    import os
    original_dir = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        # Start workflow
        await _start_workflow("test-workflow", "test.yaml")
        
        # Get session ID
        with open(".ztc/session.json") as f:
            sessions = json.load(f)
        session_id = list(sessions.keys())[0]
        
        # Answer first question
        await _submit_answer(session_id, "John Doe")
        
        # Verify session still exists
        with open(".ztc/session.json") as f:
            sessions = json.load(f)
        assert session_id in sessions
        
        # Answer second question
        await _submit_answer(session_id, "30")
        
        # Verify session deleted after completion
        with open(".ztc/session.json") as f:
            sessions = json.load(f)
        assert session_id not in sessions
        
    finally:
        os.chdir(original_dir)
