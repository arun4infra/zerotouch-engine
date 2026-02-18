1. Engine is reusable - Can be called from REST API, GraphQL, or any other
interface
2. MCP is just transport - Like a REST controller, it should only route
requests
3. Testing is easier - Test engine logic without MCP overhead
4. Matches your guidance - "Engine is single source of truth - no adapter- specific logic in MCP handlers"

## **Stateful client, Stateless backend**

1. After each adapter completes validation → CLI writes to platform.yaml
2. Before asking next question → CLI reads platform.yaml and passes to engine

Architecture:

CLI (libs/cli/commands/init.py)
├── After each adapter validated:
│   └── Write adapter config to platform.yaml
├── Before getting next question:
│   └── Read platform.yaml, pass to engine in state
└── Engine gets cross-adapter config from state (not filesystem)

Engine (libs/workflow_engine/engine/init_workflow.py)
├── Receives full platform config in state
├── Provides to adapters via _all_adapters_config
└── No filesystem access

## **Platform.yaml creation**
- CLI loads platform.yaml before each question
- CLI injects it into state as platform_adapters_config
- Engine receives it in state (no filesystem access)
- Engine provides it to adapters via _all_adapters_config
- Init scripts are the "validation gate"
- Only save config after it's validated
1. ✅ Engine always returns validation_scripts key - Even if empty list (for
adapters with no scripts)
2. ✅ CLI checks for key presence - if "validation_scripts" in result instead
of if result.get("validation_scripts")
3. ✅ All adapters return validation results

## **Engine auto-fills defaults silently.Only prompt for non-default fields**
1. Engine loops internally until hitting a field that needs user input
2. CLI saves to platform.yaml after each adapter completes (even with all
defaults)
3. No auto-derived display - User never sees "(auto-selected)" messages