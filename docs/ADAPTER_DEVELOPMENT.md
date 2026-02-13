# Adapter Development Guide

This guide explains how to create new adapters for the ZTC engine.

## Overview

Adapters are self-contained modules that provide specific infrastructure capabilities (cloud provider, OS, networking). Each adapter:

- Declares capabilities it provides and requires
- Collects user inputs via interactive prompts
- Generates manifests and configuration files
- Defines lifecycle scripts (pre-work, bootstrap, post-work, validation)

## Adapter Structure

```
ztc/adapters/my-adapter/
├── adapter.py              # Adapter implementation
├── adapter.yaml            # Metadata and capability declarations
├── config.py               # Pydantic configuration model
├── templates/              # Jinja2 templates
│   └── manifest.yaml.j2
└── scripts/                # Embedded scripts
    ├── pre_work/           # Scripts before adapter bootstrap
    ├── bootstrap/          # Core adapter responsibility scripts
    ├── post_work/          # Scripts after adapter bootstrap
    └── validation/         # Validation scripts
```

## Step 1: Create Adapter Metadata

Create `adapter.yaml` with capability declarations:

```yaml
name: my-adapter
version: 1.0.0
phase: foundation  # foundation, networking, platform, services
selection_group: my_category
is_default: false
group_prompt: "Select my adapter"
group_help: "Description of what this adapter does"

provides:
  - capability: my-capability
    version: v1.0

requires:
  - capability: upstream-capability
    version: v1.0

supported_versions:
  - v1.0.0
  - v1.1.0

default_version: v1.0.0
config_schema: schema.json
output_schema: output-schema.json
```

## Step 2: Define Configuration Model

Create `config.py` with Pydantic model:

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class MyAdapterConfig(BaseModel):
    """Configuration for my adapter"""
    
    version: str = Field(..., description="Adapter version")
    api_token: str = Field(..., description="API token for authentication")
    server_ips: List[str] = Field(..., description="List of server IPs")
    
    class Config:
        extra = "forbid"  # Reject unknown fields
```

## Step 3: Implement Adapter Class

Create `adapter.py`:

```python
from ztc.adapters.base import PlatformAdapter, InputPrompt, AdapterOutput, ScriptReference, PipelineStage
from ztc.engine.context import ContextSnapshot
from .config import MyAdapterConfig
from typing import List

class MyAdapter(PlatformAdapter):
    """My adapter implementation"""
    
    @property
    def config_model(self):
        """Return Pydantic model for config validation"""
        return MyAdapterConfig
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Return list of interactive prompts for user input"""
        return [
            InputPrompt(
                name="api_token",
                prompt="Enter API token",
                type="password",
                help_text="Your API token for authentication"
            ),
            InputPrompt(
                name="server_ips",
                prompt="Enter server IPs (comma-separated)",
                type="string",
                help_text="List of server IP addresses"
            )
        ]
    
    def pre_work_scripts(self) -> List[ScriptReference]:
        """Scripts to run before adapter bootstrap"""
        return [
            ScriptReference(
                package="ztc.adapters.my_adapter.scripts.pre_work",
                resource="setup.sh",
                description="Setup infrastructure",
                context_data={
                    "api_token": self.config["api_token"],
                    "server_ips": self.config["server_ips"]
                }
            )
        ]
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """Core adapter responsibility scripts"""
        return []
    
    def post_work_scripts(self) -> List[ScriptReference]:
        """Scripts to run after adapter bootstrap"""
        return []
    
    def validation_scripts(self) -> List[ScriptReference]:
        """Validation scripts (always run, cache_key: null)"""
        return []
    
    async def render(self, ctx: ContextSnapshot) -> AdapterOutput:
        """Generate manifests and capability data"""
        config = MyAdapterConfig(**self.config)
        
        # Access upstream capability data
        # upstream_data = ctx.get_capability_data(Capability.UPSTREAM_CAPABILITY)
        
        # Render templates
        template = self.jinja_env.get_template("my-adapter/manifest.yaml.j2")
        manifest_content = template.render(
            api_token=config.api_token,
            server_ips=config.server_ips
        )
        
        # Return adapter output
        return AdapterOutput(
            manifests={
                "manifest.yaml": manifest_content
            },
            capability_data={
                # Capability.MY_CAPABILITY: MyCapabilityData(...)
            },
            stages=[
                PipelineStage(
                    name="my_adapter_setup",
                    description="Setup my adapter",
                    script=ScriptReference(
                        package="ztc.adapters.my_adapter.scripts.bootstrap",
                        resource="install.sh",
                        description="Install my adapter"
                    )
                )
            ]
        )
```

## Step 4: Create Templates

Create Jinja2 templates in `templates/`:

```yaml
# templates/manifest.yaml.j2
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-adapter-config
data:
  api_token: {{ api_token }}
  server_ips: {{ server_ips | join(',') }}
```

## Step 5: Create Scripts

Scripts read context data via `$ZTC_CONTEXT_FILE` environment variable:

```bash
#!/usr/bin/env bash
# scripts/pre_work/setup.sh
set -euo pipefail

# Validate context file exists
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE environment variable not set" >&2
    exit 1
fi

# Parse context with jq
API_TOKEN=$(jq -r '.api_token' "$ZTC_CONTEXT_FILE")
SERVER_IPS=$(jq -r '.server_ips[]' "$ZTC_CONTEXT_FILE")

# Core logic
echo "Setting up with API token: ${API_TOKEN:0:10}..."
for ip in $SERVER_IPS; do
    echo "Configuring server: $ip"
done
```

## Step 6: Register Adapter

Add adapter to `ztc/adapters/__init__.py`:

```python
from .my_adapter.adapter import MyAdapter

__all__ = ['MyAdapter']
```

## Step 7: Write Tests

Create unit tests:

```python
# tests/unit/test_my_adapter.py
import pytest
from ztc.adapters.my_adapter.adapter import MyAdapter
from ztc.adapters.my_adapter.config import MyAdapterConfig

def test_config_validation():
    """Test adapter config validation"""
    config = MyAdapterConfig(
        version="v1.0.0",
        api_token="test_token",
        server_ips=["192.168.1.1"]
    )
    assert config.version == "v1.0.0"

def test_required_inputs():
    """Test adapter required inputs"""
    adapter = MyAdapter({"version": "v1.0.0"})
    inputs = adapter.get_required_inputs()
    assert len(inputs) > 0
```

Create integration tests:

```python
# tests/integration/test_my_adapter.py
import pytest
from ztc.adapters.my_adapter.adapter import MyAdapter
from ztc.engine.context import PlatformContext

@pytest.mark.asyncio
async def test_adapter_render():
    """Test adapter rendering"""
    config = {
        "version": "v1.0.0",
        "api_token": "test_token",
        "server_ips": ["192.168.1.1"]
    }
    
    adapter = MyAdapter(config)
    context = PlatformContext()
    snapshot = context.snapshot()
    
    output = await adapter.render(snapshot)
    
    assert "manifest.yaml" in output.manifests
    assert len(output.stages) > 0
```

## Capability System

### Defining Capabilities

Add capability to `ztc/interfaces/capabilities.py`:

```python
from pydantic import BaseModel
from enum import StrEnum

class Capability(StrEnum):
    MY_CAPABILITY = "my-capability"

class MyCapabilityData(BaseModel):
    """Strict contract for my-capability providers"""
    field1: str
    field2: int

CAPABILITY_CONTRACTS[Capability.MY_CAPABILITY] = MyCapabilityData
```

### Providing Capabilities

In your adapter's `render()` method:

```python
return AdapterOutput(
    manifests={...},
    capability_data={
        Capability.MY_CAPABILITY: MyCapabilityData(
            field1="value1",
            field2=42
        )
    },
    stages=[...]
)
```

### Requiring Capabilities

Access upstream capability data in `render()`:

```python
async def render(self, ctx: ContextSnapshot) -> AdapterOutput:
    # Get upstream capability data
    upstream = ctx.get_capability_data(Capability.UPSTREAM_CAPABILITY)
    
    # Use upstream data
    value = upstream.field1
```

## Best Practices

### 1. Adapter Independence

Each adapter must be fully self-contained:
- No cross-adapter code dependencies
- Inline helper functions in scripts
- No shared script libraries

### 2. Context Over Arguments

Scripts read JSON context files instead of CLI arguments:
- Type-safe data passing
- Auditability
- Security (sensitive data isolated)

### 3. Core Logic Preservation

When extracting scripts from existing systems:
- Keep core business logic unchanged
- Only adapt input/output mechanisms
- Inline helper functions

### 4. Validation

- Use Pydantic models for config validation
- Validate capability data against contracts
- Test with invalid inputs

### 5. Error Handling

- Provide helpful error messages
- Include remediation hints
- Use ZTC exception classes

## Example: Minimal Adapter

Here's a complete minimal adapter:

```python
# adapter.py
from ztc.adapters.base import PlatformAdapter, InputPrompt, AdapterOutput
from ztc.engine.context import ContextSnapshot
from pydantic import BaseModel
from typing import List

class MinimalConfig(BaseModel):
    version: str
    name: str

class MinimalAdapter(PlatformAdapter):
    @property
    def config_model(self):
        return MinimalConfig
    
    def get_required_inputs(self) -> List[InputPrompt]:
        return [
            InputPrompt(
                name="name",
                prompt="Enter name",
                type="string"
            )
        ]
    
    def pre_work_scripts(self) -> List[ScriptReference]:
        return []
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        return []
    
    def post_work_scripts(self) -> List[ScriptReference]:
        return []
    
    def validation_scripts(self) -> List[ScriptReference]:
        return []
    
    async def render(self, ctx: ContextSnapshot) -> AdapterOutput:
        config = MinimalConfig(**self.config)
        
        return AdapterOutput(
            manifests={
                "config.yaml": f"name: {config.name}\n"
            },
            capability_data={},
            stages=[]
        )
```

## Testing Your Adapter

```bash
# Run adapter tests
poetry run pytest tests/unit/test_my_adapter.py -v
poetry run pytest tests/integration/test_my_adapter.py -v

# Test in full workflow
cat > platform.yaml <<EOF
adapters:
  my-adapter:
    version: v1.0.0
    api_token: test_token
    server_ips:
      - 192.168.1.1
EOF

poetry run ztc render
poetry run ztc validate
```

## Troubleshooting

### Adapter Not Discovered

Ensure adapter is registered in `ztc/adapters/__init__.py` and has `adapter.yaml`.

### Template Not Found

Templates must be in `templates/` directory and accessed via adapter prefix:

```python
template = self.jinja_env.get_template("my-adapter/manifest.yaml.j2")
```

### Script Validation Fails

Scripts must exist in package at instantiation time. Use `ScriptReference` with correct package path.

### Capability Not Found

Ensure capability is declared in `adapter.yaml` provides/requires and defined in `capabilities.py`.

## Resources

- [Base Adapter Class](../ztc/adapters/base.py)
- [Capability Contracts](../ztc/interfaces/capabilities.py)
- [Example Adapters](../ztc/adapters/)
- [Integration Tests](../tests/integration/)
