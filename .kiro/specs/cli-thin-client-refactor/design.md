# Design Document: CLI Thin Client Refactor

## Overview

This design refactors the ZeroTouch CLI from a thick client with embedded business logic to a thin presentation layer. The CLI will directly import and use workflow_engine modules instead of communicating via MCP protocol. All business logic (platform config management, session state, validation orchestration, prerequisite checks) moves into the workflow_engine core, making it reusable for future API or programmatic usage.

## Architecture

### Current Architecture (Before)

```
┌─────────────────────────────────────┐
│           CLI (ztp_cli)             │
│  ┌──────────────────────────────┐   │
│  │  InitOrchestrator            │   │
│  │  - platform.yaml I/O         │   │
│  │  - session state I/O         │   │
│  │  - .env parsing              │   │
│  │  - validation orchestration  │   │
│  │  - prerequisite checks       │   │
│  └──────────────────────────────┘   │
│              ↓ MCP Protocol          │
│  ┌──────────────────────────────┐   │
│  │  WorkflowMCPClient           │   │
│  │  - JSON serialization        │   │
│  │  - stdio transport           │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
                ↓
┌─────────────────────────────────────┐
│      MCP Server (workflow_mcp)      │
│  ┌──────────────────────────────┐   │
│  │  MCP Tool Handlers           │   │
│  │  - init_start                │   │
│  │  - init_answer               │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
                ↓
┌─────────────────────────────────────┐
│    Workflow Engine (workflow_engine)│
│  ┌──────────────────────────────┐   │
│  │  InitWorkflow                │   │
│  │  - Question generation       │   │
│  │  - Answer processing         │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
```

### Target Architecture (After)

```
┌─────────────────────────────────────┐
│           CLI (ztp_cli)             │
│  ┌──────────────────────────────┐   │
│  │  InitCommand                 │   │
│  │  - Display questions (Rich)  │   │
│  │  - Collect input (prompts)   │   │
│  │  - Format output (colors)    │   │
│  │  - Show spinners             │   │
│  └──────────────────────────────┘   │
│              ↓ Via Bridge            │
│  ┌──────────────────────────────┐   │
│  │  engine_bridge.py            │   │
│  │  - Centralized imports       │   │
│  │  - Single point of access    │   │
│  │  - Re-exports engine APIs    │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
                ↓
┌─────────────────────────────────────┐
│    Workflow Engine (workflow_engine)│
│  ┌──────────────────────────────┐   │
│  │  orchestration/              │   │
│  │  - InitWorkflowOrchestrator  │   │
│  │  - ValidationOrchestrator    │   │
│  │  - PrerequisiteChecker       │   │
│  ├──────────────────────────────┤   │
│  │  services/                   │   │
│  │  - PlatformConfigService     │   │
│  │  - SessionStateService       │   │
│  │  - ValidationService         │   │
│  ├──────────────────────────────┤   │
│  │  storage/                    │   │
│  │  - FilesystemStore           │   │
│  ├──────────────────────────────┤   │
│  │  parsers/                    │   │
│  │  - EnvFileParser             │   │
│  │  - YAMLParser                │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
```

## Components and Interfaces

### 1. CLI Layer (ztp_cli)

**engine_bridge.py** - Centralized bridge for workflow_engine imports
```python
"""Bridge module for workflow_engine imports.

This module provides a single point of access to workflow_engine functionality,
centralizing all imports and re-exporting the public API for CLI usage.
"""

# Orchestrators
from workflow_engine.orchestration.init_workflow_orchestrator import InitWorkflowOrchestrator
from workflow_engine.orchestration.validation_orchestrator import ValidationOrchestrator
from workflow_engine.orchestration.prerequisite_checker import PrerequisiteChecker

# Services
from workflow_engine.services.platform_config_service import PlatformConfigService
from workflow_engine.services.session_state_service import SessionStateService
from workflow_engine.services.validation_service import ValidationService

# Models
from workflow_engine.models.workflow_result import WorkflowResult
from workflow_engine.models.validation_result import ValidationResult, ScriptResult
from workflow_engine.models.prerequisite_result import PrerequisiteResult
from workflow_engine.models.platform_config import PlatformConfig, PlatformInfo

# Storage
from workflow_engine.storage.session_store import FilesystemStore

# Parsers
from workflow_engine.parsers.env_file_parser import EnvFileParser
from workflow_engine.parsers.yaml_parser import YAMLParser

__all__ = [
    # Orchestrators
    "InitWorkflowOrchestrator",
    "ValidationOrchestrator",
    "PrerequisiteChecker",
    # Services
    "PlatformConfigService",
    "SessionStateService",
    "ValidationService",
    # Models
    "WorkflowResult",
    "ValidationResult",
    "ScriptResult",
    "PrerequisiteResult",
    "PlatformConfig",
    "PlatformInfo",
    # Storage
    "FilesystemStore",
    # Parsers
    "EnvFileParser",
    "YAMLParser",
]
```

**InitCommand** - Thin presentation layer for init workflow
**InitCommand** - Thin presentation layer for init workflow
```python
from ztp_cli.engine_bridge import (
    InitWorkflowOrchestrator,
    WorkflowResult,
)

class InitCommand:
    """Handles UI for init workflow"""
    
    def __init__(self, console: Console):
        self.console = console
        self.orchestrator = InitWorkflowOrchestrator()
    
    async def run(self) -> None:
        """Execute init command with UI"""
        # Check prerequisites via engine
        if not self.orchestrator.check_prerequisites():
            self._display_prerequisite_error()
            return
        
        # Start workflow
        result = self.orchestrator.start()
        
        # Question loop
        while not result.completed:
            if result.error:
                self._display_error(result.error)
                break
            
            # Display question
            self._display_question(result.question)
            
            # Get answer from user
            answer = await self._get_user_input(result.question)
            
            # Submit to engine
            result = self.orchestrator.answer(result.state, answer)
            
            # Display validation results if present
            if result.validation_results:
                self._display_validation_results(result.validation_results)
        
        # Display completion
        if result.completed:
            self._display_success(result.platform_yaml_path)
```

### 2. Orchestration Layer (workflow_engine/orchestration/)

**InitWorkflowOrchestrator** - Coordinates init workflow
```python
class InitWorkflowOrchestrator:
    """Orchestrates init workflow with all business logic"""
    
    def __init__(
        self,
        config_service: PlatformConfigService,
        session_service: SessionStateService,
        validation_service: ValidationService,
        prerequisite_checker: PrerequisiteChecker,
        registry: AdapterRegistry
    ):
        self.config_service = config_service
        self.session_service = session_service
        self.validation_service = validation_service
        self.prerequisite_checker = prerequisite_checker
        self.registry = registry
        self.workflow = InitWorkflow(registry)
    
    def check_prerequisites(self) -> bool:
        """Check if init can run"""
        return self.prerequisite_checker.check()
    
    def start(self) -> WorkflowResult:
        """Start init workflow"""
        result = self.workflow.start()
        return WorkflowResult(
            question=result.get("question"),
            state=result.get("workflow_state"),
            completed=result.get("completed", False),
            error=result.get("error")
        )
    
    def answer(self, state: dict, answer_value: any) -> WorkflowResult:
        """Process answer and return next question"""
        # Process answer through workflow
        result = self.workflow.answer(state, answer_value)
        
        # If validation completed, save adapter config
        if "validation_scripts" in result:
            adapter_name = self._extract_adapter_name(state)
            adapter_config = self._extract_adapter_config(result)
            self.config_service.save_adapter(adapter_name, adapter_config)
        
        # Save session state for crash recovery
        if not result.get("completed"):
            self.session_service.save("init", result.get("workflow_state"))
        else:
            self.session_service.delete("init")
        
        return WorkflowResult(
            question=result.get("question"),
            state=result.get("workflow_state"),
            completed=result.get("completed", False),
            error=result.get("error"),
            validation_results=result.get("validation_scripts"),
            platform_yaml_path=result.get("platform_yaml_path")
        )
```

**ValidationOrchestrator** - Executes validation scripts
```python
class ValidationOrchestrator:
    """Orchestrates adapter validation"""
    
    def __init__(self, script_executor: ScriptExecutor):
        self.script_executor = script_executor
    
    def validate_adapter(
        self,
        adapter: BaseAdapter,
        config: dict
    ) -> ValidationResult:
        """Execute all validation scripts for adapter"""
        init_scripts = adapter.init() if hasattr(adapter, 'init') else []
        
        if not init_scripts:
            return ValidationResult(success=True, scripts=[])
        
        script_results = []
        for script_ref in init_scripts:
            result = self.script_executor.execute(script_ref)
            
            script_results.append(ScriptResult(
                description=script_ref.description,
                success=result.exit_code == 0,
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr
            ))
            
            if result.exit_code != 0:
                return ValidationResult(
                    success=False,
                    scripts=script_results,
                    error=f"{script_ref.description} failed",
                    stderr=result.stderr
                )
        
        return ValidationResult(success=True, scripts=script_results)
```

**PrerequisiteChecker** - Validates init preconditions
```python
class PrerequisiteChecker:
    """Checks prerequisites for init workflow"""
    
    def __init__(self, config_service: PlatformConfigService):
        self.config_service = config_service
    
    def check(self) -> PrerequisiteResult:
        """Check if init can run"""
        # Check if platform.yaml exists
        if self.config_service.exists():
            return PrerequisiteResult(
                success=False,
                error="Platform configuration already exists",
                message="Delete platform.yaml to reconfigure"
            )
        
        # Check if required directories can be created
        required_dirs = [
            Path(".zerotouch-cache"),
            Path("platform")
        ]
        
        for dir_path in required_dirs:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return PrerequisiteResult(
                    success=False,
                    error=f"Cannot create directory: {dir_path}",
                    message=str(e)
                )
        
        return PrerequisiteResult(success=True)
```

### 3. Service Layer (workflow_engine/services/)

**PlatformConfigService** - Manages platform.yaml
```python
class PlatformConfigService:
    """Service for platform.yaml management"""
    
    def __init__(self, config_path: Path = Path("platform/platform.yaml")):
        self.config_path = config_path
        self.yaml_parser = YAMLParser()
    
    def exists(self) -> bool:
        """Check if platform.yaml exists"""
        return self.config_path.exists()
    
    def load(self) -> PlatformConfig:
        """Load platform configuration"""
        if not self.exists():
            raise FileNotFoundError(f"Platform config not found: {self.config_path}")
        
        data = self.yaml_parser.load(self.config_path)
        return PlatformConfig(**data)
    
    def save(self, config: PlatformConfig) -> None:
        """Save platform configuration"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.yaml_parser.save(self.config_path, config.model_dump())
    
    def save_adapter(self, adapter_name: str, adapter_config: dict) -> None:
        """Incrementally save adapter config"""
        if self.exists():
            config = self.load()
        else:
            config = PlatformConfig(
                version="1.0",
                platform=PlatformInfo(organization="", app_name=""),
                adapters={}
            )
        
        config.adapters[adapter_name] = adapter_config
        self.save(config)
    
    def load_adapters(self) -> dict:
        """Load only adapter configs for cross-adapter access"""
        if not self.exists():
            return {}
        
        config = self.load()
        return config.adapters
```

**SessionStateService** - Manages workflow state
```python
class SessionStateService:
    """Service for session state management"""
    
    def __init__(self, store: SessionStore):
        self.store = store
    
    async def save(self, session_id: str, state: dict) -> None:
        """Save workflow state"""
        await self.store.save(session_id, state)
    
    async def load(self, session_id: str) -> Optional[dict]:
        """Load workflow state"""
        return await self.store.load(session_id)
    
    async def delete(self, session_id: str) -> None:
        """Delete workflow state"""
        await self.store.delete(session_id)
    
    async def exists(self, session_id: str) -> bool:
        """Check if session exists"""
        state = await self.load(session_id)
        return state is not None
```

**ValidationService** - Validation coordination
```python
class ValidationService:
    """Service for validation coordination"""
    
    def __init__(self, orchestrator: ValidationOrchestrator):
        self.orchestrator = orchestrator
    
    def validate(self, adapter: BaseAdapter, config: dict) -> ValidationResult:
        """Validate adapter configuration"""
        return self.orchestrator.validate_adapter(adapter, config)
```

### 4. Storage Layer (workflow_engine/storage/)

**FilesystemStore** - Already exists, move from CLI
```python
# Move from ztp_cli/storage.py to workflow_engine/storage/session_store.py
# No changes needed - already implements SessionStore interface
```

### 5. Parser Layer (workflow_engine/parsers/)

**EnvFileParser** - Parse .env files
```python
class EnvFileParser:
    """Parser for .env files"""
    
    def parse(self, file_path: Path) -> dict:
        """Parse .env file into dictionary"""
        if not file_path.exists():
            return {}
        
        env_vars = {}
        content = file_path.read_text()
        
        for line in content.splitlines():
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Remove quotes
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                env_vars[key] = value
        
        return env_vars
    
    def validate(self, env_vars: dict) -> ValidationResult:
        """Validate environment variable formats"""
        errors = []
        
        for key, value in env_vars.items():
            # Check key format (uppercase, underscores)
            if not key.isupper() or not all(c.isalnum() or c == '_' for c in key):
                errors.append(f"Invalid key format: {key}")
            
            # Check value is not empty
            if not value:
                errors.append(f"Empty value for key: {key}")
        
        if errors:
            return ValidationResult(success=False, errors=errors)
        
        return ValidationResult(success=True)
```

**YAMLParser** - Parse YAML files
```python
class YAMLParser:
    """Parser for YAML files"""
    
    def load(self, file_path: Path) -> dict:
        """Load YAML file"""
        import yaml
        
        with open(file_path) as f:
            return yaml.safe_load(f) or {}
    
    def save(self, file_path: Path, data: dict) -> None:
        """Save YAML file"""
        import yaml
        
        with open(file_path, 'w') as f:
            yaml.dump(data, f, sort_keys=False, default_flow_style=False)
```

## Data Models

### WorkflowResult
```python
@dataclass
class WorkflowResult:
    """Result from workflow operation"""
    question: Optional[dict] = None
    state: Optional[dict] = None
    completed: bool = False
    error: Optional[str] = None
    validation_results: Optional[List[ScriptResult]] = None
    platform_yaml_path: Optional[Path] = None
```

### ValidationResult
```python
@dataclass
class ValidationResult:
    """Result from validation"""
    success: bool
    scripts: List[ScriptResult] = field(default_factory=list)
    error: Optional[str] = None
    stderr: Optional[str] = None
```

### ScriptResult
```python
@dataclass
class ScriptResult:
    """Result from script execution"""
    description: str
    success: bool
    exit_code: int
    stdout: str
    stderr: str
```

### PrerequisiteResult
```python
@dataclass
class PrerequisiteResult:
    """Result from prerequisite check"""
    success: bool
    error: Optional[str] = None
    message: Optional[str] = None
```

### PlatformConfig
```python
class PlatformConfig(BaseModel):
    """Platform configuration model"""
    version: str
    platform: PlatformInfo
    adapters: Dict[str, dict]

class PlatformInfo(BaseModel):
    """Platform metadata"""
    organization: str
    app_name: str
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Platform Config Round Trip
*For any* valid platform configuration, saving then loading should produce an equivalent configuration.
**Validates: Requirements 2.5**

### Property 2: Session State Round Trip
*For any* valid workflow state, saving then loading should produce an equivalent state.
**Validates: Requirements 3.5**

### Property 3: Adapter Config Incremental Save
*For any* platform configuration and new adapter config, saving the adapter incrementally should result in the adapter being present in the loaded configuration.
**Validates: Requirements 2.3, 2.4**

### Property 4: Env File Parsing Consistency
*For any* valid .env file content, parsing should extract all KEY=VALUE pairs correctly.
**Validates: Requirements 4.1, 4.2, 4.3**

### Property 5: Invalid Env Vars Rejected
*For any* environment variable with invalid format (lowercase keys, empty values), validation should reject it.
**Validates: Requirements 4.4**

### Property 6: Validation Script Execution
*For any* adapter with validation scripts, executing validation should run all scripts and return results for each.
**Validates: Requirements 5.2**

### Property 7: Validation Failure Returns Errors
*For any* validation script that fails, the validation result should include stdout and stderr.
**Validates: Requirements 5.3**

### Property 8: Validation Success Marks Validated
*For any* adapter where all validation scripts pass, the validation result should indicate success.
**Validates: Requirements 5.4**

### Property 9: Prerequisite Check Detects Existing Config
*For any* system state where platform.yaml exists, prerequisite check should return failure.
**Validates: Requirements 6.2, 6.3**

### Property 10: Prerequisite Check Validates Directories
*For any* required directory that cannot be created, prerequisite check should return failure with error details.
**Validates: Requirements 6.4**

### Property 11: Engine Returns Structured Errors
*For any* error condition in the engine, the returned error should be a structured object without ANSI formatting.
**Validates: Requirements 11.1, 11.5**

### Property 12: Engine Returns Native Python Objects
*For any* engine function call from CLI, the returned data should be native Python objects (dict, list, str) not JSON strings.
**Validates: Requirements 1.4**

### Property 13: Programmatic API Returns Unformatted Data
*For any* programmatic call to engine APIs, returned data should contain no Rich formatting or ANSI codes.
**Validates: Requirements 9.5**

## Error Handling

### Engine Error Handling
- All engine functions return structured error objects (dataclasses or Pydantic models)
- Errors include error type, message, and context (file paths, adapter names, etc.)
- No ANSI codes or terminal formatting in error messages
- Stack traces logged but not included in error objects

### CLI Error Handling
- CLI receives structured errors from engine
- CLI formats errors with Rich console (colors, styling)
- CLI displays contextual help (log file locations, resolution steps)
- CLI handles KeyboardInterrupt for graceful cancellation

### Validation Error Handling
- Validation failures include script name, exit code, stdout, stderr
- Logs written to .zerotouch-cache/init-logs/ with timestamps
- CLI displays log file path for debugging
- User prompted to retry or abort

### File I/O Error Handling
- File not found errors include full path
- Permission errors include directory and required permissions
- YAML parse errors include line number and syntax issue
- All file errors wrapped in service-specific exceptions

## Testing Strategy

### Unit Testing
- Test each service independently with mocked dependencies
- Test parsers with various valid and invalid inputs
- Test orchestrators with mocked services
- Test CLI presentation with mocked engine calls
- Use InMemoryStore for testing without filesystem

### Property-Based Testing
- Minimum 100 iterations per property test
- Each test tagged with: **Feature: cli-thin-client-refactor, Property {number}: {property_text}**
- Use hypothesis (Python) for generating test data
- Properties test universal behaviors across all inputs

### Integration Testing
- Test full init workflow end-to-end
- Test crash recovery with interrupted workflows
- Test validation with real adapter scripts
- Test backward compatibility with existing commands

### Testing Separation
- Engine tests have no CLI dependencies (no Rich, no Typer)
- Engine tests use InMemoryStore or filesystem mocks
- CLI tests mock all engine calls
- Property tests focus on engine logic, unit tests on CLI presentation
