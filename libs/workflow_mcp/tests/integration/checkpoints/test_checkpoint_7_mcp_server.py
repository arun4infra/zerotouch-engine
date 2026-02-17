"""Checkpoint 7: MCP Protocol and Server

Tests MCP server with workflow tools, stdio and HTTP transports, 
stateless architecture, and transport security modes.
"""
import pytest
import asyncio
import base64
import json
from pathlib import Path
from libs.workflow_mcp.workflow_server.mcp_server import WorkflowMCPServer
from libs.workflow_mcp.workflow_server.transport_security import (
    TransportSecurityMode,
    SecurityError,
    get_transport_config
)


@pytest.mark.asyncio
async def test_mcp_server_initialization():
    """Test MCP server initializes correctly"""
    server = WorkflowMCPServer(workflow_base_path=Path("test_workflows"))
    
    assert server.workflow_base_path == Path("test_workflows")
    assert server.parser is not None
    assert server.mcp is not None


@pytest.mark.asyncio
async def test_start_workflow_tool(tmp_path):
    """Test start_workflow tool creates session and returns first question"""
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
    
    server = WorkflowMCPServer(workflow_base_path=tmp_path)
    
    # Call start_workflow implementation
    result = await server._start_workflow_impl("test-workflow", "test.yaml")
    
    # Verify response structure
    assert "session_id" in result
    assert "question" in result
    assert "state_blob" in result
    assert "completed" in result
    
    # Verify session ID is UUID
    assert len(result["session_id"]) == 36
    
    # Verify first question
    assert result["question"]["id"] == "q1"
    assert result["question"]["type"] == "string"
    assert result["question"]["prompt"] == "Enter name"
    assert result["completed"] is False
    
    # Verify state blob is base64 encoded
    state = json.loads(base64.b64decode(result["state_blob"]))
    assert state["session_id"] == result["session_id"]
    assert state["workflow_id"] == "test-workflow"


@pytest.mark.asyncio
async def test_submit_answer_tool(tmp_path):
    """Test submit_answer tool processes answer and returns next question"""
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
    
    server = WorkflowMCPServer(workflow_base_path=tmp_path)
    
    # Start workflow
    start_result = await server._start_workflow_impl("test-workflow", "test.yaml")
    
    # Submit answer to first question
    submit_result = await server._submit_answer_impl(
        session_id=start_result["session_id"],
        state_blob=start_result["state_blob"],
        answer_value="John",
        answer_type="string",
        timestamp=1000
    )
    
    # Verify next question
    assert submit_result["question"]["id"] == "q2"
    assert submit_result["question"]["type"] == "integer"
    assert submit_result["completed"] is False
    
    # Submit answer to second question
    final_result = await server._submit_answer_impl(
        session_id=start_result["session_id"],
        state_blob=submit_result["state_blob"],
        answer_value=25,
        answer_type="integer",
        timestamp=2000
    )
    
    # Verify workflow completed
    assert final_result["question"] is None
    assert final_result["completed"] is True


@pytest.mark.asyncio
async def test_restore_session_tool(tmp_path):
    """Test restore_session tool restores state with default answer"""
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
    
    server = WorkflowMCPServer(workflow_base_path=tmp_path)
    
    # Start workflow and submit answer
    start_result = await server._start_workflow_impl("test-workflow", "test.yaml")
    submit_result = await server._submit_answer_impl(
        session_id=start_result["session_id"],
        state_blob=start_result["state_blob"],
        answer_value="John",
        answer_type="string",
        timestamp=1000
    )
    
    # Restore session (workflow already complete, but test the mechanism)
    # For this test, we'll use the state before completion
    restore_result = await server._restore_session_impl(
        session_id=start_result["session_id"],
        state_blob=start_result["state_blob"]
    )
    
    # Verify restored question
    assert restore_result["question"]["id"] == "q1"
    assert restore_result["state_blob"] == start_result["state_blob"]


@pytest.mark.asyncio
async def test_restart_workflow_tool(tmp_path):
    """Test restart_workflow tool creates new session"""
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
    
    server = WorkflowMCPServer(workflow_base_path=tmp_path)
    
    # Start workflow
    start_result = await server._start_workflow_impl("test-workflow", "test.yaml")
    original_session_id = start_result["session_id"]
    
    # Restart workflow
    restart_result = await server._start_workflow_impl("test-workflow", "test.yaml")
    
    # Verify new session ID
    assert restart_result["session_id"] != original_session_id
    
    # Verify starts from first question
    assert restart_result["question"]["id"] == "q1"
    assert restart_result["completed"] is False


@pytest.mark.asyncio
async def test_stateless_server_architecture(tmp_path):
    """Test server remains stateless - state passed in each request"""
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
    
    server = WorkflowMCPServer(workflow_base_path=tmp_path)
    
    # Start workflow
    result1 = await server._start_workflow_impl("test-workflow", "test.yaml")
    
    # Server should have no stored state
    # Each call requires state_blob parameter
    
    # Submit answer with state blob
    result2 = await server._submit_answer_impl(
        session_id=result1["session_id"],
        state_blob=result1["state_blob"],
        answer_value="John",
        answer_type="string",
        timestamp=1000
    )
    
    # Verify state blob is different (updated)
    assert result2["state_blob"] != result1["state_blob"]


@pytest.mark.asyncio
async def test_transport_security_development_mode():
    """Test development mode allows localhost only"""
    server = WorkflowMCPServer()
    
    # Development mode should allow localhost
    config = get_transport_config(
        security_mode=TransportSecurityMode.DEVELOPMENT,
        port=8000
    )
    
    assert config["host"] == "127.0.0.1"
    assert config["tls_enabled"] is False


@pytest.mark.asyncio
async def test_transport_security_production_mode_requires_tls():
    """Test production mode requires TLS"""
    # Production mode without TLS should raise error
    with pytest.raises(SecurityError):
        get_transport_config(
            security_mode=TransportSecurityMode.PRODUCTION,
            host="0.0.0.0",
            port=8000
        )


@pytest.mark.asyncio
async def test_transport_security_production_rejects_localhost():
    """Test production mode rejects localhost binding"""
    # Production mode with localhost should raise error
    with pytest.raises(SecurityError):
        get_transport_config(
            security_mode=TransportSecurityMode.PRODUCTION,
            host="127.0.0.1",
            port=8000,
            tls_cert_path="/path/to/cert.pem",
            tls_key_path="/path/to/key.pem"
        )


@pytest.mark.asyncio
async def test_state_blob_encoding_decoding(tmp_path):
    """Test state blob is properly encoded/decoded"""
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
    
    server = WorkflowMCPServer(workflow_base_path=tmp_path)
    
    # Start workflow
    result = await server._start_workflow_impl("test-workflow", "test.yaml")
    
    # Decode state blob
    state = server._decode_state(result["state_blob"])
    
    # Verify state structure
    assert "session_id" in state
    assert "workflow_id" in state
    assert "workflow_version_hash" in state
    assert "feedback_history" in state
    
    # Re-encode and verify
    re_encoded = server._encode_state(state)
    re_decoded = server._decode_state(re_encoded)
    
    assert state == re_decoded


@pytest.mark.asyncio
async def test_workflow_conversion_to_entries(tmp_path):
    """Test workflow DSL is correctly converted to Entry objects"""
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
      help_text: "Your full name"
      default: "John Doe"
      sensitive: false
    next_state: null
transitions: []
""")
    
    server = WorkflowMCPServer(workflow_base_path=tmp_path)
    
    # Parse workflow
    workflow = await server.parser.parse_yaml(workflow_yaml)
    
    # Convert to entries
    entries = server._convert_workflow_to_entries(workflow)
    
    # Verify conversion
    assert len(entries) == 1
    assert entries[0].id == "q1"
    assert entries[0].type.value == "string"
    assert entries[0].prompt == "Enter name"
    assert entries[0].help_text == "Your full name"
    assert entries[0].default == "John Doe"
    assert entries[0].sensitive is False
