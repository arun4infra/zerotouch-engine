
## Test Scenario Understanding

**Test 1: CLI→MCP→Engine (Local E2E)**
- CLI commands (`ztc init/render/bootstrap/validate`) act as thin orchestrators
- Each command calls multiple MCP tools via JSON-RPC
- MCP server routes tool calls to appropriate handlers (Adapter/Platform/Render/Bootstrap/Validation)
- Handlers invoke workflow engine components (DependencyResolver, BootstrapExecutor, PipelineGenerator)
- Validates: CLI refactoring successful, all business logic moved to MCP layer, same artifacts as legacy

**Test 2: IDE→MCP→Engine (Chat-Driven)**
- AI agent (Claude/Cursor) discovers 19 MCP tools via tool listing
- User issues natural language commands ("List adapters", "Generate platform.yaml")
- AI translates intent into appropriate tool calls with correct parameters
- Same MCP server/handler/engine flow as Test 1
- Validates: Tools are granular enough for AI orchestration, AI can compose multi-step workflows, no CLI required

**Key Difference**: Test 1 validates CLI refactoring; Test 2 validates AI-driven infrastructure orchestration capability.