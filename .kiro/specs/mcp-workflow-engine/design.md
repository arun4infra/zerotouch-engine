# Design Document: MCP Workflow Engine

## Overview

The MCP Workflow Engine is a Python-based backend service that orchestrates conditional question flows for infrastructure provisioning workflows. The engine implements a stateless server architecture where clients maintain session state, communicating via the Model Context Protocol (MCP) over JSON-RPC. The design adapts the QuestionPathTraverser pattern from the reference TypeScript implementation, translating it to Python idioms while maintaining the core architectural principles of stateful navigation, immutable feedback records, and observer-based event notifications.

The engine integrates with existing zerotouch-engine adapters (Hetzner, ArgoCD, etc.) through a translation layer that converts PlatformAdapter InputPrompt objects to workflow DSL question nodes. This enables dynamic workflow generation from adapter metadata while maintaining separation between workflow orchestration and infrastructure provisioning logic.

## Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────┐
│                   CLI (Presentation Layer)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Typer Commands│  │ Formatters   │  │ Display Logic    │  │
│  │ (Lifecycle)   │  │ (Errors/Info)│  │ (Visual Output)  │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │ FilesystemStore│  │ JSON-RPC     │                         │
│  │ (.ztc/session) │  │ Client       │                         │
│  └──────────────┘  └──────────────┘                         │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ stdio/HTTP transport
                            │ (JSON-RPC messages)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   MCP (Protocol Layer)                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  MCPServer │ JSON-RPC Parser │ Transports │ Observer │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Function calls
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Workflow Engine (Core + Adapters)               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   Core Components                     │   │
│  │  QuestionPathTraverser │ Observer │ Deferred Ops     │   │
│  │  AutomaticAnswer │ LevelTracker │ Feedback          │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Models & Parsing                         │   │
│  │  Entry │ EntryData │ WorkflowDSL │ Validation       │   │
│  │  DSL Parser │ Expression Evaluator │ SecretResolver  │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Adapter Integration                      │   │
│  │  PlatformAdapter │ AdapterRegistry │ Translator      │   │
│  │  Hetzner │ Cilium │ ArgoCD │ GitHub │ ... (all)     │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### State Management Architecture

The engine follows a **client-side state management** pattern where:
- **MCP Server**: Stateless, processes each request independently
- **CLI Client**: Maintains session state in `.ztc/session.json`
- **State Blob**: Serialized session state passed with each request
- **Session Restoration**: Server reconstructs state from client-provided blob

This architecture enables:
- Horizontal scaling of MCP servers
- Session persistence across server restarts
- Multiple concurrent sessions per client
- Simplified server deployment (no state storage)

### Communication Flow

```
Client                          MCP Server
  │                                 │
  │  start_workflow()               │
  ├────────────────────────────────>│
  │                                 │ Parse DSL
  │                                 │ Initialize traverser
  │                                 │ Get first question
  │                                 │
  │  {question, session_id, state}  │
  │<────────────────────────────────┤
  │                                 │
  │  Save state to .ztc/session.json│
  │                                 │
  │  submit_answer(state, answer)   │
  ├────────────────────────────────>│
  │                                 │ Deserialize state
  │                                 │ Validate answer
  │                                 │ Update traverser
  │                                 │ Get next question
  │                                 │
  │  {question, state}              │
  │<────────────────────────────────┤
  │                                 │
  │  Save updated state             │
  │                                 │
```

## Components and Interfaces

### Core Components

#### 1. QuestionPathTraverser

**Purpose**: Stateful navigation component managing workflow traversal with level tracking.

**Responsibilities**:
- Maintain current position in workflow tree
- Track level stack for nested workflows
- Manage feedback history (immutable records)
- Coordinate automatic answer handling
- Emit observer notifications for state changes
- Support session serialization/deserialization

**Key Methods**:
```python
class QuestionPathTraverser:
    def __init__(
        self,
        question_path: QuestionPath,
        planning_context: PlanningContext,
        automatic_answer_provider: AutomaticAnswerProvider,
        answer_handler: AnswerHandler,
        question_path_provider: QuestionPathProvider,
        planning_data_provider: PlanningDataProvider
    ):
        """Initialize traverser with dependencies"""
        
    async def start_async(self, timestamp: int) -> None:
        """Start traversal, auto-answer initial questions"""
        
    def get_current_question(self) -> Optional[Entry]:
        """Get current question requiring user input"""
        
    async def answer_current_question_async(
        self, 
        entry_data: EntryData, 
        timestamp: int
    ) -> None:
        """Answer current question and advance"""
        
    async def restore_async(
        self,
        feedbacks: List[QuestionPathFeedback],
        proposals: List[QuestionPathFeedback],
        operations: List[OnQuestionPathCompleteOperation],
        timestamp: int
    ) -> None:
        """Restore session from serialized state"""
        
    def get_feedback_array(self) -> List[QuestionPathFeedback]:
        """Get committed feedback history"""
        
    def serialize(self) -> Dict[str, Any]:
        """Serialize traverser state to JSON-compatible dict"""
```

**State Fields**:
- `current_question`: Current Entry requiring answer
- `current_feedback_id`: Monotonic feedback counter
- `feedback_map`: Map of feedback_id → QuestionPathFeedback
- `current_level`: QuestionPathLevelTracker instance
- `level_stack`: Stack of QuestionPathLevelTracker for nested workflows
- `on_question_path_complete_operations`: Deferred operations list
- `feedback_proposal_array`: Proposed answers for restoration

#### 2. QuestionPathLevelTracker

**Purpose**: Track position within a single workflow level.

**Responsibilities**:
- Store current entry and index
- Store level entries list
- Store planning context for level
- Support serialization for state persistence

**Structure**:
```python
@dataclass
class QuestionPathLevelTracker:
    stopped_at_entry: Entry
    stopped_at_entry_index: int
    level_entries: List[Entry]
    planning_context: PlanningContext
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize level tracker state"""
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuestionPathLevelTracker':
        """Deserialize level tracker state"""
```

#### 3. SessionStore (Strategy Pattern)

**Purpose**: Abstract interface for session persistence.

**Implementations**:
- **FilesystemStore** (CLI Client): Persists to `.ztc/session.json`
- **InMemoryStore** (MCP Server): Testing-only, no persistence

**Interface**:
```python
class SessionStore(ABC):
    @abstractmethod
    async def save(self, session_id: str, state: Dict[str, Any]) -> None:
        """Save session state"""
        
    @abstractmethod
    async def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session state"""
        
    @abstractmethod
    async def delete(self, session_id: str) -> None:
        """Delete session state"""
```

**FilesystemStore Implementation**:
```python
class FilesystemStore(SessionStore):
    def __init__(self, base_path: Path = Path(".ztc")):
        self.base_path = base_path
        
    async def save(self, session_id: str, state: Dict[str, Any]) -> None:
        """Atomic write to .ztc/session.json"""
        session_file = self.base_path / "session.json"
        temp_file = session_file.with_suffix(".tmp")
        
        # Write to temp file
        async with aiofiles.open(temp_file, 'w') as f:
            await f.write(json.dumps(state, indent=2))
        
        # Atomic rename
        temp_file.replace(session_file)
```

#### 4. Feedback System

**Purpose**: Immutable record of user answers with context.

**QuestionPathFeedback Structure**:
```python
@dataclass(frozen=True)
class QuestionPathFeedback:
    question_path: QuestionPath
    feedback_id: int
    timestamp: int
    entry: Entry  # Question that was answered
    entry_data: EntryData  # Answer value
    planning_context: PlanningContext
    is_automatic: bool = False
    is_sensitive: bool = False
    
    def equals(self, other_data: EntryData) -> bool:
        """Compare answer data for equality"""
        
    def to_dict(self) -> Dict[str, Any]:
        """Serialize feedback to JSON-compatible dict"""
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuestionPathFeedback':
        """Deserialize feedback from dict"""
```

**Feedback History Management**:
- Feedback objects are immutable after creation
- Stored in `feedback_map: Dict[int, QuestionPathFeedback]`
- Ordered by `feedback_id` (monotonic counter)
- Serialized with session state for restoration
- Sensitive fields marked with `is_sensitive=True`

#### 5. Observer Pattern for Events

**Purpose**: Notify clients of workflow state changes.

**Observer Interface**:
```python
class QuestionPathTraverserObserver(ABC):
    @abstractmethod
    async def receive_notification_async(
        self, 
        notification: QuestionPathTraverserNotification
    ) -> None:
        """Handle notification from traverser"""
```

**Notification Types**:
```python
@dataclass
class QuestionPathNextQuestionReady:
    """Emitted when next question requires user input"""
    current_question: Entry

@dataclass
class QuestionPathFeedbackEntered:
    """Emitted when answer is submitted"""
    feedback: QuestionPathFeedback
    is_new_feedback: bool

@dataclass
class QuestionPathFeedbackUpdated:
    """Emitted when current answer is modified"""
    feedback: QuestionPathFeedback
    is_new_feedback: bool

@dataclass
class QuestionPathCompleted:
    """Emitted when workflow completes"""
    question_path: QuestionPath
    reason: QuestionPathCompletedReason  # Closed, Canceled

@dataclass
class SessionRestored:
    """Emitted when session is restored"""
    session_id: str
    feedback_count: int
```

**MCP Server Observer Implementation**:
```python
from mcp.server.session import ServerSession
from mcp.types import Notification

class MCPServerObserver(QuestionPathTraverserObserver):
    def __init__(self, session: ServerSession):
        self.session = session
        
    async def receive_notification_async(
        self, 
        notification: QuestionPathTraverserNotification
    ) -> None:
        """Convert notification to MCP notification using official SDK"""
        # Use official MCP notification format
        await self.session.send_notification(
            Notification(
                method=f"workflow/{notification.__class__.__name__}",
                params=notification.to_dict()
            )
        )
```

#### 6. Workflow DSL Parser

**Purpose**: Parse and validate YAML workflow definitions.

**Pydantic Models**:
```python
class QuestionNode(BaseModel):
    id: str
    type: Literal["string", "integer", "boolean", "choice"]
    prompt: str
    help_text: Optional[str] = None
    default: Optional[Any] = None
    validation: Optional[ValidationRules] = None
    automatic_answer: Optional[str] = None  # Expression
    sensitive: bool = False
    
class ValidationRules(BaseModel):
    regex: Optional[str] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    choices: Optional[List[str]] = None
    
class TransitionNode(BaseModel):
    from_state: str
    to_state: str
    condition: Optional[str] = None  # Expression
    
class WorkflowDSL(BaseModel):
    version: str
    workflow_id: str
    states: Dict[str, StateNode]
    transitions: List[TransitionNode]
    
    @validator('version')
    def validate_version(cls, v):
        if v not in ["1.0.0"]:
            raise ValueError(f"Unsupported version: {v}")
        return v
```

**Parser Implementation**:
```python
class WorkflowDSLParser:
    def __init__(self):
        self.schema_cache: Dict[str, WorkflowDSL] = {}
        
    async def parse_yaml(self, yaml_path: Path) -> WorkflowDSL:
        """Parse and validate YAML workflow"""
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        
        try:
            workflow = WorkflowDSL(**data)
            return workflow
        except ValidationError as e:
            raise WorkflowDSLError(
                f"Invalid workflow DSL: {e}",
                line_number=self._extract_line_number(e)
            )
    
    def _extract_line_number(self, error: ValidationError) -> Optional[int]:
        """Extract line number from Pydantic validation error"""
        # Implementation uses ruamel.yaml for line tracking
```

#### 7. Adapter Integration Layer

**Purpose**: Translate PlatformAdapter InputPrompt objects to workflow DSL questions.

**InputPrompt to Question Translation**:
```python
class AdapterQuestionTranslator:
    def translate_input_prompt(
        self, 
        prompt: InputPrompt,
        adapter_name: str
    ) -> QuestionNode:
        """Convert InputPrompt to QuestionNode"""
        return QuestionNode(
            id=f"{adapter_name}.{prompt.name}",
            type=self._map_type(prompt.type),
            prompt=prompt.prompt,
            help_text=prompt.help_text,
            default=prompt.default,
            validation=self._build_validation(prompt),
            sensitive=prompt.type == "password"
        )
    
    def _map_type(self, prompt_type: str) -> str:
        """Map InputPrompt type to workflow DSL type"""
        mapping = {
            "string": "string",
            "password": "string",
            "choice": "choice",
            "integer": "integer",
            "boolean": "boolean"
        }
        return mapping[prompt_type]
```

**Dynamic Adapter Loading**:
```python
class AdapterWorkflowGenerator:
    def __init__(self, adapter_registry: AdapterRegistry):
        self.registry = adapter_registry
        self.translator = AdapterQuestionTranslator()
        
    async def generate_workflow_from_adapters(
        self, 
        adapter_names: List[str]
    ) -> WorkflowDSL:
        """Generate workflow DSL from adapter metadata"""
        states = {}
        transitions = []
        
        for adapter_name in adapter_names:
            adapter = self.registry.get_adapter(adapter_name)
            inputs = adapter.get_required_inputs()
            
            for input_prompt in inputs:
                question = self.translator.translate_input_prompt(
                    input_prompt, 
                    adapter_name
                )
                states[question.id] = StateNode(
                    question=question,
                    next_state=self._determine_next_state(...)
                )
        
        return WorkflowDSL(
            version="1.0.0",
            workflow_id=f"adapters_{hash(tuple(adapter_names))}",
            states=states,
            transitions=transitions
        )
```

**Dynamic Choices via get_dynamic_choices()**:
```python
class DynamicChoiceResolver:
    async def resolve_choices(
        self, 
        adapter: PlatformAdapter,
        input_prompt: InputPrompt,
        context: PlatformContext
    ) -> List[str]:
        """Resolve dynamic choices at runtime"""
        if hasattr(input_prompt, 'get_dynamic_choices'):
            return await input_prompt.get_dynamic_choices(context)
        return input_prompt.choices or []
```

#### 8. Automatic Answer Provider

**Purpose**: Determine if question should be auto-answered.

**Implementation**:
```python
class AutomaticAnswerProvider:
    def __init__(
        self, 
        buffer_provider: QuestionPathBufferProvider,
        expression_evaluator: ExpressionEvaluator
    ):
        self.buffer_provider = buffer_provider
        self.evaluator = expression_evaluator
        
    async def get_automatic_answer_async(
        self, 
        entry: Entry
    ) -> Optional[EntryData]:
        """Get automatic answer if configured"""
        if not entry.automatic_answer:
            return None
        
        try:
            # Evaluate expression against previous answers
            result = await self.evaluator.evaluate(
                entry.automatic_answer,
                self.buffer_provider.get_buffers()
            )
            return self._convert_to_entry_data(result, entry.type)
        except ExpressionError:
            # Expression failed, present question to user
            return None
```

#### 9. Deferred Operations Registry

**Purpose**: Register operations that execute on workflow completion.

**Implementation**:
```python
class DeferredOperationsRegistry:
    def __init__(self):
        self.operations: List[OnQuestionPathCompleteOperation] = []
        
    def register(self, operation: OnQuestionPathCompleteOperation) -> None:
        """Register deferred operation"""
        self.operations.append(operation)
        
    async def execute_all(
        self, 
        feedback_history: List[QuestionPathFeedback],
        platform_context: PlatformContext
    ) -> None:
        """Execute all registered operations in order"""
        for operation in self.operations:
            await operation.execute(feedback_history, platform_context)
    
    def rollback_all(self) -> None:
        """Rollback all operations on failure"""
        for operation in reversed(self.operations):
            operation.rollback()
    
    def clear(self) -> None:
        """Clear all registered operations"""
        self.operations.clear()
```

**Operation Types**:
```python
@dataclass
class OnQuestionPathCompleteOperation(ABC):
    feedback_id: int
    
    @abstractmethod
    async def execute(
        self, 
        feedback_history: List[QuestionPathFeedback],
        platform_context: PlatformContext
    ) -> None:
        """Execute operation"""
        
    @abstractmethod
    def rollback(self) -> None:
        """Rollback operation on failure"""
```

### MCP Protocol Integration

#### MCP Tools Implementation

Workflow operations are exposed as MCP tools following the official SDK pattern:

**start_workflow tool**:
```python
from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

mcp = FastMCP("Workflow Engine")

@mcp.tool()
async def start_workflow(workflow_id: str, workflow_dsl_path: str) -> dict:
    """Start a new workflow session
    
    Args:
        workflow_id: Unique identifier for the workflow
        workflow_dsl_path: Path to workflow YAML definition
        
    Returns:
        Dictionary with session_id, question, and state_blob
    """
    # Parse workflow DSL
    workflow = await parser.parse_yaml(workflow_dsl_path)
    
    # Initialize traverser
    traverser = QuestionPathTraverser(workflow, ...)
    await traverser.start_async(timestamp())
    
    # Get first question
    question = traverser.get_current_question()
    
    # Serialize state
    state = traverser.serialize()
    
    return {
        "session_id": str(uuid.uuid4()),
        "question": {
            "id": question.id,
            "type": question.type,
            "prompt": question.prompt,
            "sensitive": question.sensitive
        },
        "state_blob": base64.b64encode(json.dumps(state).encode()).decode()
    }
```

**submit_answer tool**:
```python
@mcp.tool()
async def submit_answer(
    session_id: str,
    state_blob: str,
    answer_value: str,
    timestamp: int
) -> dict:
    """Submit answer and get next question
    
    Args:
        session_id: Session identifier
        state_blob: Base64-encoded serialized state
        answer_value: User's answer
        timestamp: Answer submission timestamp
        
    Returns:
        Dictionary with next question and updated state_blob
    """
    # Deserialize state
    state = json.loads(base64.b64decode(state_blob))
    
    # Restore traverser
    traverser = await restore_traverser_from_state(state)
    
    # Submit answer
    entry_data = EntryData(value=answer_value)
    await traverser.answer_current_question_async(entry_data, timestamp)
    
    # Get next question
    question = traverser.get_current_question()
    
    # Serialize updated state
    new_state = traverser.serialize()
    
    return {
        "question": {
            "id": question.id,
            "type": question.type,
            "prompt": question.prompt
        } if question else None,
        "state_blob": base64.b64encode(json.dumps(new_state).encode()).decode(),
        "completed": question is None
    }
```

**restore_session tool**:
```python
@mcp.tool()
async def restore_session(session_id: str, state_blob: str) -> dict:
    """Restore workflow session from state blob
    
    Args:
        session_id: Session identifier
        state_blob: Base64-encoded serialized state
        
    Returns:
        Dictionary with current question (with default) and state_blob
    """
    # Deserialize state
    state = json.loads(base64.b64decode(state_blob))
    
    # Restore traverser
    traverser = await restore_traverser_from_state(state)
    
    # Get current question with previous answer as default
    question = traverser.get_current_question()
    feedback = traverser.get_feedback_for_question(question.id)
    
    return {
        "question": {
            "id": question.id,
            "type": question.type,
            "prompt": question.prompt,
            "default": feedback.entry_data.value if feedback else None
        },
        "state_blob": state_blob
    }
```

**restart_workflow tool**:
```python
@mcp.tool()
async def restart_workflow(workflow_id: str) -> dict:
    """Restart workflow from beginning
    
    Args:
        workflow_id: Workflow identifier
        
    Returns:
        Same as start_workflow - new session with first question
    """
    # Discard any existing state, start fresh
    return await start_workflow(workflow_id, get_workflow_path(workflow_id))
```

#### Transport Configuration

**stdio Transport** (Local CLI):
```python
from mcp.server.stdio import stdio_server
from mcp.server.fastmcp import FastMCP

async def run_stdio_server():
    """Run MCP server with stdio transport"""
    mcp = FastMCP("Workflow Engine")
    
    # Register workflow tools
    register_workflow_tools(mcp)
    
    # Run with stdio transport (official SDK)
    async with stdio_server() as (read_stream, write_stream):
        await mcp.run(read_stream, write_stream)
```

**HTTP Transport** (Network):
```python
from mcp.server.fastmcp import FastMCP

async def run_http_server(security_mode: TransportSecurityMode):
    """Run MCP server with HTTP transport"""
    mcp = FastMCP("Workflow Engine")
    
    # Register workflow tools
    register_workflow_tools(mcp)
    
    # Configure transport based on security mode
    if security_mode == TransportSecurityMode.PRODUCTION:
        # Require TLS in production
        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",
            port=8000,
            # TLS configuration enforced at transport level
        )
    else:
        # Development mode - localhost only
        mcp.run(
            transport="streamable-http",
            host="127.0.0.1",
            port=8000
        )
```

**Security Modes**:
```python
from enum import Enum

class TransportSecurityMode(Enum):
    DEVELOPMENT = "development"  # HTTP on localhost only
    PRODUCTION = "production"    # HTTPS/TLS mandatory

def validate_transport_security(
    transport_type: str,
    security_mode: TransportSecurityMode,
    host: str
) -> None:
    """Enforce security mode constraints"""
    if security_mode == TransportSecurityMode.PRODUCTION:
        if transport_type == "streamable-http":
            # In production, require TLS (enforced by transport config)
            # and reject localhost-only bindings
            if host in ("127.0.0.1", "localhost"):
                raise SecurityError(
                    "Production mode requires network-accessible binding"
                )
```

## Data Models

### Session State Schema

```python
{
    "session_id": "uuid-string",
    "workflow_id": "hetzner-setup",
    "workflow_version_hash": "sha256-hash",
    "current_question_id": "hetzner.server_ips",
    "feedback_history": [
        {
            "feedback_id": 0,
            "timestamp": 1234567890,
            "entry_id": "hetzner.api_token",
            "entry_data": {
                "type": "string",
                "value": "$HETZNER_API_TOKEN"  # Environment variable reference
            },
            "is_automatic": false,
            "is_sensitive": true
        }
    ],
    "level_stack": [
        {
            "stopped_at_entry_id": "parent.question",
            "stopped_at_entry_index": 2,
            "level_entries": ["parent.q1", "parent.q2", "parent.q3"],
            "planning_context": {}
        }
    ],
    "current_level": {
        "stopped_at_entry_id": "hetzner.server_ips",
        "stopped_at_entry_index": 1,
        "level_entries": ["hetzner.api_token", "hetzner.server_ips"],
        "planning_context": {}
    },
    "deferred_operations": [
        {
            "type": "adapter_activation",
            "feedback_id": 5,
            "adapter_name": "hetzner",
            "operation_data": {}
        }
    ],
    "feedback_proposals": []
}
```

### Secrets Management

**Environment Variable References**:
```python
class SecretResolver:
    def resolve_secret(self, reference: str) -> str:
        """Resolve environment variable reference"""
        if reference.startswith("$"):
            env_var = reference[1:]
            value = os.getenv(env_var)
            if not value:
                raise SecretNotFoundError(
                    f"Environment variable {env_var} not set"
                )
            return value
        return reference
    
    def mask_sensitive_value(self, value: str) -> str:
        """Mask sensitive value for display"""
        return "***REDACTED***"
```

**Serialization with Secrets**:
```python
def serialize_feedback(feedback: QuestionPathFeedback) -> Dict[str, Any]:
    """Serialize feedback, storing env var references for secrets"""
    data = {
        "feedback_id": feedback.feedback_id,
        "timestamp": feedback.timestamp,
        "entry_id": feedback.entry.id,
        "is_automatic": feedback.is_automatic,
        "is_sensitive": feedback.is_sensitive
    }
    
    if feedback.is_sensitive:
        # Store environment variable reference, not actual value
        data["entry_data"] = {
            "type": "string",
            "value": f"${feedback.entry.env_var_name}"
        }
    else:
        data["entry_data"] = feedback.entry_data.to_dict()
    
    return data
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property Reflection

After analyzing all acceptance criteria, I identified several areas where properties can be consolidated:

**Consolidation Opportunities**:
1. Properties 1.2 and 1.3 (level tracking and position updates) can be combined into a single comprehensive property about state consistency during traversal
2. Properties 3.4, 3.5, 3.6, 3.7 (individual event emissions) can be combined into one property about event emission for all state changes
3. Properties 4.2, 4.3, 4.4 (feedback object fields) can be combined into one property about feedback object completeness
4. Properties 7.3, 7.4, 7.5 (answer validation and state updates) can be combined into one property about validation behavior
5. Properties 12.2, 12.3, 12.4 (serialization fields) are subsumed by property 12.5 (round-trip preservation)
6. Properties 13.2 and 13.3 (level stack push/pop) can be combined into one property about level stack consistency

**Redundancy Elimination**:
- Property 7.6 (session restoration round-trip) is redundant with property 12.5 (serialization round-trip)
- Property 15.1 (restore from blob) is redundant with property 12.5
- Property 10.2 (restart presents first question) is redundant with property 7.7 (restart always begins from first)

After reflection, the following properties provide unique validation value:

### Correctness Properties

**Property 1: Traverser state consistency during navigation**
*For any* workflow and any sequence of answer submissions, the QuestionPathTraverser should maintain consistent state where current level tracking, position information, and level stack accurately reflect the navigation history.
**Validates: Requirements 1.2, 1.3**

**Property 2: Session state round-trip preservation**
*For any* workflow session state, serializing then deserializing should produce an equivalent state with identical session ID, workflow ID, current question, feedback history, level stack, and deferred operations.
**Validates: Requirements 1.5, 4.7, 7.6, 12.1, 12.2, 12.3, 12.4, 12.5, 13.5, 14.8, 15.1**

**Property 3: Filesystem atomic write safety**
*For any* session state and any concurrent write operations, the FilesystemStore should ensure that either the complete new state is written or the previous state remains intact, with no partial writes visible.
**Validates: Requirements 2.4**

**Property 4: Observer notification completeness**
*For any* workflow state change (answer submission, question presentation, workflow completion, session restoration) and any set of registered observers, all observers should receive the corresponding notification.
**Validates: Requirements 3.2, 3.4, 3.5, 3.6, 3.7**

**Property 5: Feedback object uniqueness and immutability**
*For any* sequence of answer submissions, each Feedback_Object should have a unique ID, and attempting to modify any field after creation should fail.
**Validates: Requirements 4.1, 4.5**

**Property 6: Feedback object completeness**
*For any* answer submission, the created Feedback_Object should contain timestamp, question context (ID, text, type), answer value, and validation status.
**Validates: Requirements 4.2, 4.3, 4.4**

**Property 7: Feedback history ordering**
*For any* sequence of answer submissions, the feedback list should maintain insertion order with monotonically increasing feedback IDs.
**Validates: Requirements 4.6**

**Property 8: Workflow DSL state ID uniqueness**
*For any* valid workflow DSL, all state identifiers should be unique within the workflow.
**Validates: Requirements 5.3**

**Property 9: Workflow DSL validation correctness**
*For any* workflow DSL, validation should succeed if and only if the DSL conforms to the schema, and validation failures should include line numbers.
**Validates: Requirements 5.6, 5.7**

**Property 10: JSON-RPC message handling**
*For any* valid JSON-RPC request, the MCP server should parse it successfully and return a valid JSON-RPC response; for any invalid request, parsing should fail with an error response containing code and message.
**Validates: Requirements 6.2, 6.3, 6.5**

**Property 11: Session ID uniqueness**
*For any* workflow start operation, a unique session ID should be generated that differs from all previously generated session IDs.
**Validates: Requirements 7.1, 10.3**

**Property 12: Workflow start response completeness**
*For any* workflow start, the response should contain the first question, a unique session ID, and a serialized state blob.
**Validates: Requirements 7.2**

**Property 13: Answer validation state preservation**
*For any* answer submission, if validation succeeds then state should be updated and next question returned; if validation fails then state should remain unchanged and error returned.
**Validates: Requirements 7.3, 7.4, 7.5, 11.2, 11.3, 11.4**

**Property 14: Workflow restart initialization**
*For any* workflow restart, the engine should discard current session state, generate a new session ID, and present the first question from the workflow DSL.
**Validates: Requirements 7.7, 10.1, 10.2, 10.3**

**Property 15: Automatic answer skipping**
*For any* question with a valid automatic answer expression, the question should not be presented to the user, a Feedback_Object with auto-answer flag should be created, and the engine should proceed to the next question.
**Validates: Requirements 8.1, 8.2, 8.3**

**Property 16: Automatic answer fallback**
*For any* question with an automatic answer expression that fails evaluation, the question should be presented to the user for manual input.
**Validates: Requirements 8.5**

**Property 17: Adapter loading and context construction**
*For any* workflow state requiring an adapter, the adapter should be loaded from AdapterRegistry and PlatformContext should be constructed from session answers with correct mapping to adapter input prompts.
**Validates: Requirements 9.2, 9.3, 9.4**

**Property 18: Cross-adapter answer accessibility**
*For any* set of adapters with cross-adapter dependencies, answers from one adapter should be accessible to other adapters through the merged PlatformContext.
**Validates: Requirements 9.5, 9.6**

**Property 19: Adapter failure state preservation**
*For any* adapter execution failure, the workflow state should remain unchanged and an error should be returned.
**Validates: Requirements 9.8**

**Property 20: Dynamic choice resolution**
*For any* adapter input prompt with dynamic choices, calling get_dynamic_choices() should fetch choices at runtime based on current context.
**Validates: Requirements 9.9**

**Property 21: InputPrompt to question translation**
*For any* PlatformAdapter InputPrompt, translation should produce a valid Workflow_DSL question node with correct type mapping and field preservation.
**Validates: Requirements 9.11**

**Property 22: Nested workflow level stack consistency**
*For any* nested workflow navigation, entering a child workflow should push current level to stack (growing by one), and completing child workflow should pop level from stack (shrinking by one) and resume parent.
**Validates: Requirements 13.2, 13.3**

**Property 23: Nested workflow context isolation and inheritance**
*For any* nested workflow, each level should maintain separate context, child workflows should inherit parent context on entry, and context modifications in child should be visible to parent after return.
**Validates: Requirements 13.4, 13.6, 13.7**

**Property 24: Deferred operations execution order**
*For any* set of registered deferred operations, successful workflow completion should execute all operations in registration order with access to feedback history and PlatformContext.
**Validates: Requirements 14.2, 14.4, 14.5**

**Property 25: Deferred operations cancellation**
*For any* workflow cancellation, all registered deferred operations should be discarded without execution.
**Validates: Requirements 14.3**

**Property 26: Deferred operations rollback**
*For any* deferred operation failure, all previously executed operations should be rolled back and an error with operation details should be returned.
**Validates: Requirements 14.6, 14.7**

**Property 27: Session restoration default answers**
*For any* restored session, presenting a previously answered question should include the previous answer as the default value, and accepting the default should proceed to next question.
**Validates: Requirements 15.2, 15.3**

**Property 28: Session restoration answer modification**
*For any* restored session, modifying a default answer should update the feedback history and proceed to the next question.
**Validates: Requirements 15.4**

**Property 29: Session restoration committed feedback only**
*For any* serialized session, only committed feedback history should be included, excluding any speculative or proposed answers.
**Validates: Requirements 15.6**

**Property 30: Sensitive field environment variable storage**
*For any* sensitive question field, serialization should store an environment variable reference (e.g., $VAR_NAME) instead of the actual secret value.
**Validates: Requirements 16.2, 16.3**

**Property 31: Sensitive field runtime resolution**
*For any* environment variable reference in session state, deserialization should resolve it to the actual value from the environment, and PlatformContext construction should contain resolved values.
**Validates: Requirements 16.4, 16.5**

**Property 32: Sensitive field redaction**
*For any* sensitive field, logging and event emission should contain redacted values (***REDACTED***), and feedback objects should have is_sensitive flag set.
**Validates: Requirements 16.6, 16.7, 16.8**

**Property 33: Sensitive field deferred resolution**
*For any* deferred operation accessing sensitive fields, values should be resolved from environment variables at execution time, not at registration time.
**Validates: Requirements 16.9**

**Property 34: Production mode TLS enforcement**
*For any* HTTP connection attempt in production mode without TLS, the MCP server should reject the connection.
**Validates: Requirements 17.3**

## Error Handling

### Error Categories

**1. Validation Errors**
- Invalid answer type (string provided for integer question)
- Answer fails regex validation
- Answer outside allowed range
- Invalid choice selection
- Cross-field validation failure

**Error Response**:
```python
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Answer must match pattern: ^[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}$",
        "field": "hetzner.server_ip",
        "validation_rule": "regex"
    }
}
```

**2. Workflow DSL Errors**
- Invalid YAML syntax
- Schema validation failure
- Duplicate state IDs
- Missing required fields
- Invalid transition conditions

**Error Response**:
```python
{
    "error": {
        "code": "WORKFLOW_DSL_ERROR",
        "message": "Duplicate state ID: hetzner.api_token",
        "line_number": 42,
        "file": "workflows/hetzner-setup.yaml"
    }
}
```

**3. Session Errors**
- Session not found
- Invalid session state blob
- Session deserialization failure
- Version mismatch (workflow DSL changed)

**Error Response**:
```python
{
    "error": {
        "code": "SESSION_ERROR",
        "message": "Workflow DSL version mismatch: session uses v1.0.0, current is v1.1.0",
        "session_id": "uuid-here",
        "expected_version": "v1.0.0",
        "actual_version": "v1.1.0"
    }
}
```

**4. Adapter Errors**
- Adapter not found in registry
- Adapter initialization failure
- Dynamic choice resolution failure
- PlatformContext construction failure

**Error Response**:
```python
{
    "error": {
        "code": "ADAPTER_ERROR",
        "message": "Failed to load adapter: hetzner",
        "adapter_name": "hetzner",
        "cause": "Adapter module not found"
    }
}
```

**5. Secret Resolution Errors**
- Environment variable not set
- Secret reference invalid format
- Secret resolution failure during deserialization

**Error Response**:
```python
{
    "error": {
        "code": "SECRET_ERROR",
        "message": "Environment variable not set: HETZNER_API_TOKEN",
        "env_var": "HETZNER_API_TOKEN",
        "field": "hetzner.api_token"
    }
}
```

**6. Transport Errors**
- Invalid JSON-RPC message
- Unsupported JSON-RPC version
- Method not found
- TLS required but not provided (production mode)

**Error Response**:
```python
{
    "jsonrpc": "2.0",
    "error": {
        "code": -32700,  # JSON-RPC parse error
        "message": "Invalid JSON-RPC message: missing 'method' field"
    },
    "id": null
}
```

### Error Handling Strategy

**Stateless Error Recovery**:
- Server never persists error state
- Client receives error response with unchanged state blob
- Client can retry with corrected input
- No server-side cleanup required

**Atomic State Updates**:
- State updates are all-or-nothing
- Validation failure → no state change
- Adapter failure → no state change
- Deferred operation failure → rollback all operations

**Error Propagation**:
- Errors bubble up through layers with context
- Each layer adds relevant information
- Top-level error handler formats JSON-RPC response
- Sensitive information redacted from error messages

## Testing Strategy

### Dual Testing Approach

The testing strategy combines unit tests for specific examples and edge cases with property-based tests for universal properties across all inputs.

**Unit Tests**:
- Specific workflow examples (Hetzner setup, ArgoCD deployment)
- Edge cases (empty workflows, single-question workflows)
- Error conditions (invalid DSL, missing secrets)
- Integration points (adapter loading, MCP transport)

**Property-Based Tests**:
- Universal properties across all workflows
- Comprehensive input coverage through randomization
- Minimum 100 iterations per property test
- Each test references design document property

### Property Test Configuration

**Library**: Hypothesis (Python property-based testing library)

**Test Structure**:
```python
from hypothesis import given, strategies as st
import pytest

@given(
    workflow=st.workflows(),  # Custom strategy
    answers=st.lists(st.answer_data())
)
def test_property_2_session_state_round_trip(workflow, answers):
    """
    Feature: mcp-workflow-engine
    Property 2: Session state round-trip preservation
    
    For any workflow session state, serializing then deserializing
    should produce an equivalent state.
    """
    # Setup
    traverser = create_traverser(workflow)
    for answer in answers:
        await traverser.answer_current_question_async(answer, timestamp())
    
    # Serialize
    state = traverser.serialize()
    
    # Deserialize
    restored_traverser = create_traverser(workflow)
    await restored_traverser.restore_async(
        state['feedback_history'],
        state['feedback_proposals'],
        state['deferred_operations'],
        timestamp()
    )
    
    # Assert equivalence
    assert traverser.get_current_question() == restored_traverser.get_current_question()
    assert traverser.get_feedback_array() == restored_traverser.get_feedback_array()
    assert traverser.current_level == restored_traverser.current_level
    assert len(traverser.level_stack) == len(restored_traverser.level_stack)
```

**Custom Strategies**:
```python
@st.composite
def workflows(draw):
    """Generate random valid workflows"""
    num_states = draw(st.integers(min_value=1, max_value=10))
    states = {}
    for i in range(num_states):
        states[f"state_{i}"] = draw(question_nodes())
    return WorkflowDSL(
        version="1.0.0",
        workflow_id=draw(st.uuids()).hex,
        states=states,
        transitions=draw(st.lists(transitions(states.keys())))
    )

@st.composite
def question_nodes(draw):
    """Generate random question nodes"""
    return QuestionNode(
        id=draw(st.text(min_size=1)),
        type=draw(st.sampled_from(["string", "integer", "boolean", "choice"])),
        prompt=draw(st.text(min_size=1)),
        validation=draw(st.one_of(st.none(), validation_rules()))
    )
```

### Test Coverage Requirements

**Unit Test Coverage**:
- All error conditions (validation, DSL, session, adapter, secret, transport)
- All workflow DSL features (states, transitions, conditions, automatic answers)
- All adapter integration points (loading, context construction, dynamic choices)
- All MCP protocol endpoints (start, submit, restore, restart)
- All observer notifications (answer submitted, question presented, completed, restored)

**Property Test Coverage**:
- All 34 correctness properties from design document
- Minimum 100 iterations per property
- Edge cases handled by generators (empty workflows, single questions, deeply nested)

### Integration Testing

**End-to-End Workflow Tests**:
```python
@pytest.mark.asyncio
async def test_hetzner_workflow_end_to_end():
    """Test complete Hetzner setup workflow"""
    # Start workflow
    response = await mcp_client.start_workflow("hetzner-setup")
    assert response['question']['id'] == "hetzner.api_token"
    
    # Submit API token
    response = await mcp_client.submit_answer(
        response['session_id'],
        response['state_blob'],
        {"value": "$HETZNER_API_TOKEN"}
    )
    assert response['question']['id'] == "hetzner.server_ips"
    
    # Submit server IPs
    response = await mcp_client.submit_answer(
        response['session_id'],
        response['state_blob'],
        {"value": "192.168.1.1,192.168.1.2"}
    )
    
    # Verify workflow completion
    assert response['completed'] == True
    assert len(response['deferred_operations']) > 0
```

**Adapter Integration Tests**:
```python
@pytest.mark.asyncio
async def test_adapter_workflow_generation():
    """Test workflow generation from adapter metadata"""
    adapters = ["hetzner", "cilium", "talos"]
    generator = AdapterWorkflowGenerator(adapter_registry)
    
    workflow = await generator.generate_workflow_from_adapters(adapters)
    
    # Verify workflow structure
    assert workflow.workflow_id.startswith("adapters_")
    assert len(workflow.states) == sum(
        len(adapter.get_required_inputs()) for adapter in adapters
    )
    
    # Verify question translation
    hetzner_adapter = adapter_registry.get_adapter("hetzner")
    for input_prompt in hetzner_adapter.get_required_inputs():
        question_id = f"hetzner.{input_prompt.name}"
        assert question_id in workflow.states
        assert workflow.states[question_id].type == map_type(input_prompt.type)
```

### Performance Testing

**Property Test Performance**:
- Each property test should complete in < 10 seconds (100 iterations)
- Workflow generation should be fast (< 100ms per workflow)
- Serialization/deserialization should be fast (< 10ms per session)

**MCP Server Performance**:
- Request processing should be fast (< 100ms per request)
- Session restoration should be fast (< 50ms)
- Adapter loading should be cached (< 10ms after first load)

### Test Execution

```bash
# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run property tests only
pytest tests/property/ -v

# Run integration tests only
pytest tests/integration/ -v

# Run with coverage
pytest tests/ --cov=ztc.mcp_workflow_engine --cov-report=html

# Run specific property test
pytest tests/property/test_session_serialization.py::test_property_2_session_state_round_trip -v
```
