"""MCP Server implementation using official MCP SDK"""
from typing import Dict, Any, Optional
import uuid
import base64
import json
import time
from pathlib import Path
import anyio

from mcp.server.fastmcp import FastMCP

from workflow_engine.parser.dsl_parser import WorkflowDSLParser
from workflow_engine.core.traverser import QuestionPathTraverser
from workflow_engine.models.entry import Entry, EntryData, EntryType
from workflow_mcp.workflow_server.transport_security import (
    TransportSecurityMode,
    validate_transport_security,
    get_transport_config
)
from workflow_mcp.handlers import (
    AdapterHandler,
    PlatformHandler,
    RenderHandler,
    BootstrapHandler,
    ValidationHandler,
)


class WorkflowMCPServer:
    """MCP Server for workflow engine using FastMCP"""
    
    def __init__(self, workflow_base_path: Path = Path("workflows"), allow_write: bool = False):
        """Initialize MCP server
        
        Args:
            workflow_base_path: Base directory for workflow YAML files
            allow_write: Allow write operations (render, bootstrap, etc.)
        """
        self.workflow_base_path = workflow_base_path
        self.parser = WorkflowDSLParser()
        self.allow_write = allow_write
        
        # Create FastMCP server
        self.mcp = FastMCP("Workflow Engine", json_response=True)
        
        # Register workflow tools
        self._register_tools()
        
        # Register platform handlers
        self._register_handlers()
    
    def _register_handlers(self) -> None:
        """Register platform handlers"""
        AdapterHandler(self.mcp, self.allow_write)
        PlatformHandler(self.mcp, self.allow_write)
        RenderHandler(self.mcp, self.allow_write)
        BootstrapHandler(self.mcp, self.allow_write)
        ValidationHandler(self.mcp, self.allow_write)
    
    def _register_tools(self) -> None:
        """Register workflow tools with FastMCP"""
        
        @self.mcp.tool()
        async def start_workflow(workflow_id: str, workflow_dsl_path: str) -> dict:
            """Start a new workflow session
            
            Args:
                workflow_id: Unique identifier for the workflow
                workflow_dsl_path: Path to workflow YAML definition
                
            Returns:
                Dictionary with session_id, question, and state_blob
            """
            return await self._start_workflow_impl(workflow_id, workflow_dsl_path)
        
        @self.mcp.tool()
        async def submit_answer(
            session_id: str,
            state_blob: str,
            answer_value: Any,
            answer_type: str,
            timestamp: int
        ) -> dict:
            """Submit answer and get next question
            
            Args:
                session_id: Session identifier
                state_blob: Base64-encoded serialized state
                answer_value: User's answer
                answer_type: Type of answer (string, integer, boolean, choice)
                timestamp: Answer submission timestamp
                
            Returns:
                Dictionary with next question and updated state_blob
            """
            return await self._submit_answer_impl(
                session_id, state_blob, answer_value, answer_type, timestamp
            )
        
        @self.mcp.tool()
        async def restore_session(session_id: str, state_blob: str) -> dict:
            """Restore workflow session from state blob
            
            Args:
                session_id: Session identifier
                state_blob: Base64-encoded serialized state
                
            Returns:
                Dictionary with current question (with default) and state_blob
            """
            return await self._restore_session_impl(session_id, state_blob)
        
        @self.mcp.tool()
        async def restart_workflow(workflow_id: str, workflow_dsl_path: str) -> dict:
            """Restart workflow from beginning
            
            Args:
                workflow_id: Workflow identifier
                workflow_dsl_path: Path to workflow YAML definition
                
            Returns:
                Same as start_workflow - new session with first question
            """
            return await self._start_workflow_impl(workflow_id, workflow_dsl_path)
    
    async def _start_workflow_impl(
        self, 
        workflow_id: str, 
        workflow_dsl_path: str
    ) -> Dict[str, Any]:
        """Implementation of start_workflow tool"""
        # Parse workflow DSL
        workflow_path = self.workflow_base_path / workflow_dsl_path
        workflow = await self.parser.parse_yaml(workflow_path)
        
        # Convert workflow states to entries
        entries = self._convert_workflow_to_entries(workflow)
        
        # Initialize traverser
        traverser = QuestionPathTraverser(entries)
        await traverser.start_async(self._get_timestamp())
        
        # Get first question
        question = traverser.get_current_question()
        
        # Serialize state
        state = traverser.serialize()
        state["session_id"] = str(uuid.uuid4())
        state["workflow_id"] = workflow_id
        state["workflow_dsl_path"] = workflow_dsl_path  # Store path for restoration
        
        return {
            "session_id": state["session_id"],
            "question": self._format_question(question) if question else None,
            "state_blob": self._encode_state(state),
            "completed": question is None
        }
    
    async def _submit_answer_impl(
        self,
        session_id: str,
        state_blob: str,
        answer_value: Any,
        answer_type: str,
        timestamp: int
    ) -> Dict[str, Any]:
        """Implementation of submit_answer tool"""
        # Deserialize state
        state = self._decode_state(state_blob)
        
        # Restore traverser
        traverser = await self._restore_traverser_from_state(state)
        
        # Create entry data
        entry_data = EntryData(
            type=EntryType(answer_type),
            value=answer_value
        )
        
        # Submit answer
        await traverser.answer_current_question_async(entry_data, timestamp)
        
        # Get next question
        question = traverser.get_current_question()
        
        # Serialize updated state
        new_state = traverser.serialize()
        new_state["session_id"] = session_id
        new_state["workflow_id"] = state.get("workflow_id")
        new_state["workflow_dsl_path"] = state.get("workflow_dsl_path")  # Preserve path
        
        return {
            "question": self._format_question(question) if question else None,
            "state_blob": self._encode_state(new_state),
            "completed": question is None
        }
    
    async def _restore_session_impl(
        self,
        session_id: str,
        state_blob: str
    ) -> Dict[str, Any]:
        """Implementation of restore_session tool"""
        # Deserialize state
        state = self._decode_state(state_blob)
        
        # Restore traverser
        traverser = await self._restore_traverser_from_state(state)
        
        # Get current question
        question = traverser.get_current_question()
        
        # Get previous answer if exists
        default_value = None
        if question:
            feedback_history = traverser.get_feedback_array()
            for feedback in feedback_history:
                if feedback.entry.id == question.id:
                    default_value = feedback.entry_data.value
                    break
        
        question_data = self._format_question(question) if question else None
        if question_data and default_value is not None:
            question_data["default"] = default_value
        
        return {
            "question": question_data,
            "state_blob": state_blob
        }
    
    def _convert_workflow_to_entries(self, workflow) -> list[Entry]:
        """Convert workflow DSL to list of Entry objects"""
        entries = []
        for state_id, state in workflow.states.items():
            question = state.question
            entry = Entry(
                id=question.id,
                type=EntryType(question.type),
                prompt=question.prompt,
                help_text=question.help_text,
                default=question.default,
                automatic_answer=question.automatic_answer,
                sensitive=question.sensitive
            )
            entries.append(entry)
        return entries
    
    async def _restore_traverser_from_state(
        self, 
        state: Dict[str, Any]
    ) -> QuestionPathTraverser:
        """Restore traverser from serialized state"""
        # Load workflow DSL using stored path
        workflow_dsl_path = state.get("workflow_dsl_path")
        if not workflow_dsl_path:
            # Fallback to workflow_id.yaml for backward compatibility
            workflow_id = state.get("workflow_id")
            workflow_dsl_path = f"{workflow_id}.yaml"
        
        workflow_path = self.workflow_base_path / workflow_dsl_path
        workflow = await self.parser.parse_yaml(workflow_path)
        
        # Convert to entries
        entries = self._convert_workflow_to_entries(workflow)
        
        # Create traverser
        traverser = QuestionPathTraverser(
            entries,
            workflow_version_hash=state.get("workflow_version_hash")
        )
        
        # Restore state
        await traverser.restore_async(state, self._get_timestamp())
        
        return traverser
    
    def _format_question(self, question: Optional[Entry]) -> Optional[Dict[str, Any]]:
        """Format question for JSON response"""
        if not question:
            return None
        
        return {
            "id": question.id,
            "type": question.type.value,
            "prompt": question.prompt,
            "help_text": question.help_text,
            "default": question.default,
            "sensitive": question.sensitive
        }
    
    def _encode_state(self, state: Dict[str, Any]) -> str:
        """Encode state as base64 string"""
        json_str = json.dumps(state)
        return base64.b64encode(json_str.encode()).decode()
    
    def _decode_state(self, state_blob: str) -> Dict[str, Any]:
        """Decode base64 state blob"""
        json_str = base64.b64decode(state_blob).decode()
        return json.loads(json_str)
    
    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds"""
        return int(time.time() * 1000)
    
    async def run_stdio(self) -> None:
        """Run MCP server with stdio transport"""
        await self.mcp.run(transport="stdio")
    
    async def run_http(
        self, 
        security_mode: TransportSecurityMode = TransportSecurityMode.DEVELOPMENT,
        host: Optional[str] = None, 
        port: int = 8000,
        tls_cert_path: Optional[str] = None,
        tls_key_path: Optional[str] = None
    ) -> None:
        """Run MCP server with HTTP transport
        
        Args:
            security_mode: Security mode (development or production)
            host: Host to bind to (defaults based on security mode)
            port: Port to bind to
            tls_cert_path: Path to TLS certificate (production only)
            tls_key_path: Path to TLS private key (production only)
            
        Raises:
            SecurityError: If security constraints are violated
        """
        # Get transport configuration based on security mode
        config = get_transport_config(
            security_mode=security_mode,
            host=host,
            port=port,
            tls_cert_path=tls_cert_path,
            tls_key_path=tls_key_path
        )
        
        # Validate transport security
        validate_transport_security(
            transport_type=config["transport"],
            security_mode=security_mode,
            host=config["host"],
            tls_enabled=config.get("tls_enabled", False)
        )
        
        # Run with streamable-http transport
        await self.mcp.run(
            transport="streamable-http",
            host=config["host"],
            port=config["port"]
        )
