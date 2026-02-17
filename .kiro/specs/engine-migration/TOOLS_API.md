# MCP Tools API Reference

This document defines all MCP tools exposed by the ZeroTouch MCP server.

## Tool Naming Convention

- Use snake_case for tool names
- Use descriptive verbs: `list_`, `get_`, `create_`, `update_`, `delete_`, `validate_`, `execute_`
- Group related tools by prefix

## AdapterHandler Tools

### list_adapters

**Description**: List all available adapters with metadata

**Parameters**: None

**Returns**:
```json
{
  "adapters": [
    {
      "name": "hetzner",
      "version": "1.0.0",
      "phase": "foundation",
      "provides": ["cloud-infrastructure"],
      "requires": [],
      "description": "Hetzner cloud provider adapter"
    },
    ...
  ]
}
```

### get_adapter_inputs

**Description**: Get required input prompts for an adapter

**Parameters**:
- `adapter_name` (string, required): Name of the adapter

**Returns**:
```json
{
  "adapter_name": "hetzner",
  "inputs": [
    {
      "name": "api_token",
      "prompt": "Hetzner API Token",
      "type": "password",
      "required": true,
      "help_text": "API token from Hetzner Cloud Console"
    },
    {
      "name": "server_ips",
      "prompt": "Server IP Addresses",
      "type": "list",
      "required": true,
      "help_text": "List of server IPs to manage"
    }
  ]
}
```

### validate_adapter_config

**Description**: Validate adapter configuration against schema

**Parameters**:
- `adapter_name` (string, required): Name of the adapter
- `config` (object, required): Configuration to validate

**Returns**:
```json
{
  "valid": true,
  "errors": []
}
```

Or on failure:
```json
{
  "valid": false,
  "errors": [
    {
      "field": "api_token",
      "message": "API token must be at least 64 characters"
    }
  ]
}
```

### get_adapter_metadata

**Description**: Get detailed metadata for an adapter

**Parameters**:
- `adapter_name` (string, required): Name of the adapter

**Returns**:
```json
{
  "name": "hetzner",
  "version": "1.0.0",
  "phase": "foundation",
  "provides": [
    {
      "capability": "cloud-infrastructure",
      "version": "v1.0"
    }
  ],
  "requires": [],
  "supported_versions": ["1.0.0"],
  "default_version": "1.0.0"
}
```

## PlatformHandler Tools

### generate_platform_yaml

**Description**: Generate platform.yaml from adapter configurations

**Parameters**:
- `adapters_config` (object, required): Map of adapter_name → config

**Returns**:
```json
{
  "path": "platform.yaml",
  "adapters_count": 3,
  "content": "adapters:\n  hetzner:\n    ..."
}
```

### validate_platform_yaml

**Description**: Validate platform.yaml structure and adapter configs

**Parameters**:
- `yaml_path` (string, required): Path to platform.yaml

**Returns**:
```json
{
  "valid": true,
  "adapters_count": 3,
  "errors": []
}
```

### get_platform_status

**Description**: Get current platform configuration status

**Parameters**: None

**Returns**:
```json
{
  "platform_yaml_exists": true,
  "lock_file_exists": true,
  "generated_artifacts_exist": true,
  "adapters_configured": ["hetzner", "cilium", "talos"],
  "last_render": "2026-02-17T23:00:00Z",
  "drift_detected": false
}
```

### merge_secrets

**Description**: Merge secrets from ~/.ztc/secrets into platform config

**Parameters**:
- `platform_yaml` (string, required): Path to platform.yaml
- `secrets_file` (string, optional): Path to secrets file (default: ~/.ztc/secrets)

**Returns**:
```json
{
  "merged_count": 5,
  "adapters_updated": ["hetzner", "github", "ksops"]
}
```

## RenderHandler Tools

### render_adapters

**Description**: Render manifests for all or partial adapters

**Parameters**:
- `platform_yaml` (string, required): Path to platform.yaml
- `partial` (array, optional): List of adapter names to render (default: all)
- `debug` (boolean, optional): Preserve workspace on failure (default: false)

**Returns**:
```json
{
  "status": "success",
  "adapter_count": 3,
  "manifest_count": 47,
  "artifacts_hash": "abc123...",
  "output_path": "platform/generated",
  "adapters_rendered": ["hetzner", "cilium", "talos"]
}
```

### generate_pipeline_yaml

**Description**: Generate pipeline.yaml from adapter stages

**Parameters**:
- `platform_yaml` (string, required): Path to platform.yaml

**Returns**:
```json
{
  "status": "success",
  "stage_count": 15,
  "output_path": "platform/generated/pipeline.yaml",
  "stages": [
    {
      "name": "install-talos",
      "phase": "foundation",
      "barrier": "local"
    },
    ...
  ]
}
```

### generate_lock_file

**Description**: Generate lock file with hashes and metadata

**Parameters**:
- `platform_yaml` (string, required): Path to platform.yaml
- `artifacts_hash` (string, required): Hash of generated artifacts

**Returns**:
```json
{
  "status": "success",
  "output_path": "platform/lock.json",
  "platform_hash": "def456...",
  "artifacts_hash": "abc123...",
  "ztc_version": "1.0.0",
  "adapters": {
    "hetzner": {"version": "1.0.0", "phase": "foundation"},
    "cilium": {"version": "1.0.0", "phase": "networking"},
    "talos": {"version": "1.0.0", "phase": "os"}
  }
}
```

### extract_debug_scripts

**Description**: Extract scripts to debug directory for manual execution

**Parameters**:
- `platform_yaml` (string, required): Path to platform.yaml

**Returns**:
```json
{
  "status": "success",
  "output_path": "platform/generated/debug/scripts",
  "script_count": 23,
  "adapters": ["hetzner", "cilium", "talos", "argocd", "ksops"]
}
```

## BootstrapHandler Tools

### execute_stage

**Description**: Execute single bootstrap stage with caching and retry

**Parameters**:
- `stage_name` (string, required): Name of the stage
- `context` (object, required): Context data for the stage
- `cache_enabled` (boolean, optional): Enable stage caching (default: true)
- `retry_count` (integer, optional): Number of retries on failure (default: 3)

**Returns**:
```json
{
  "status": "success",
  "stage_name": "install-talos",
  "cached": false,
  "duration_seconds": 45,
  "exit_code": 0,
  "stdout": "...",
  "stderr": ""
}
```

Or on failure:
```json
{
  "status": "failed",
  "stage_name": "install-talos",
  "error": "Script execution failed",
  "exit_code": 1,
  "stdout": "...",
  "stderr": "Error: ..."
}
```

### get_stage_status

**Description**: Get execution status of a stage

**Parameters**:
- `stage_name` (string, required): Name of the stage

**Returns**:
```json
{
  "stage_name": "install-talos",
  "executed": true,
  "cached": true,
  "last_execution": "2026-02-17T23:00:00Z",
  "status": "success"
}
```

### list_stages

**Description**: List all stages from pipeline.yaml

**Parameters**:
- `pipeline_yaml` (string, required): Path to pipeline.yaml

**Returns**:
```json
{
  "total_stages": 15,
  "stages": [
    {
      "name": "install-talos",
      "description": "Install Talos OS on servers",
      "phase": "foundation",
      "barrier": "local",
      "required": true,
      "cache_key": "talos-install"
    },
    ...
  ]
}
```

### rollback_stage

**Description**: Rollback a failed stage (if supported)

**Parameters**:
- `stage_name` (string, required): Name of the stage to rollback

**Returns**:
```json
{
  "status": "success",
  "stage_name": "install-talos",
  "rollback_performed": true
}
```

## ValidationHandler Tools

### validate_artifacts

**Description**: Validate generated artifacts against lock file

**Parameters**:
- `lock_file` (string, required): Path to lock file

**Returns**:
```json
{
  "valid": true,
  "platform_hash_match": true,
  "artifacts_hash_match": true,
  "errors": []
}
```

Or on failure:
```json
{
  "valid": false,
  "platform_hash_match": false,
  "artifacts_hash_match": true,
  "errors": [
    {
      "type": "platform_modified",
      "message": "platform.yaml has been modified since last render"
    }
  ]
}
```

### validate_runtime_dependencies

**Description**: Check for required CLI tools (kubectl, talosctl, etc.)

**Parameters**: None

**Returns**:
```json
{
  "valid": true,
  "dependencies": [
    {
      "name": "kubectl",
      "required": true,
      "installed": true,
      "version": "1.28.0"
    },
    {
      "name": "talosctl",
      "required": true,
      "installed": true,
      "version": "1.6.0"
    },
    {
      "name": "argocd",
      "required": false,
      "installed": true,
      "version": "2.9.0"
    }
  ],
  "missing": []
}
```

### validate_cluster_access

**Description**: Validate cluster connectivity and permissions

**Parameters**:
- `kubeconfig` (string, optional): Path to kubeconfig (default: ~/.kube/config)

**Returns**:
```json
{
  "accessible": true,
  "cluster_name": "my-cluster",
  "server": "https://192.168.1.1:6443",
  "version": "v1.28.0",
  "nodes_count": 3,
  "namespaces_count": 12
}
```

## Error Handling

All tools return errors in a consistent format:

```json
{
  "status": "error",
  "error_type": "ValidationError",
  "message": "Adapter configuration is invalid",
  "details": {
    "adapter": "hetzner",
    "field": "api_token",
    "reason": "Token must be at least 64 characters"
  }
}
```

## Tool Access Control

Tools respect the `--allow-write` flag:

- **Read-only tools** (always available):
  - `list_adapters`
  - `get_adapter_inputs`
  - `get_adapter_metadata`
  - `validate_adapter_config`
  - `validate_platform_yaml`
  - `get_platform_status`
  - `get_stage_status`
  - `list_stages`
  - `validate_artifacts`
  - `validate_runtime_dependencies`
  - `validate_cluster_access`

- **Write tools** (require `--allow-write`):
  - `generate_platform_yaml`
  - `merge_secrets`
  - `render_adapters`
  - `generate_pipeline_yaml`
  - `generate_lock_file`
  - `extract_debug_scripts`
  - `execute_stage`
  - `rollback_stage`

## Tool Invocation Examples

### From CLI (Python)
```python
result = await mcp_client.call_tool("list_adapters")
print(result["adapters"])
```

### From IDE (Natural Language)
```
User: "List all available adapters"
AI: [calls list_adapters tool]
    "Available adapters: hetzner, cilium, talos, argocd, ksops..."
```

### From MCP Client (JSON-RPC)
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "list_adapters",
    "arguments": {}
  },
  "id": 1
}
```
