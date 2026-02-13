## Adapter Interface Contract

### Base Adapter Class

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any
from pydantic import BaseModel

@dataclass
class InputPrompt:
    """User input definition for adapter configuration"""
    name: str
    prompt: str
    type: str  # "string", "choice", "boolean", "password"
    default: Any = None
    choices: List[str] = None
    help_text: str = ""

@dataclass
class ScriptReference:
    """Reference to embedded script with optional context data"""
    package: str              # Python package path
    resource: str             # Script filename or enum
    context_data: Dict = None # JSON-serializable data passed to script

@dataclass
class PipelineStage:
    """Bootstrap pipeline stage definition"""
    name: str
    script: ScriptReference
    description: str = ""

@dataclass
class AdapterOutput:
    """Adapter rendering output"""
    manifests: Dict[str, str]        # filename -> content
    capability_data: Dict[str, Any]  # Capability enum -> Pydantic model
    pipeline_stages: List[PipelineStage]

class PlatformAdapter(ABC):
    """Base class for all platform adapters"""
    
    @abstractmethod
    def get_required_inputs(self) -> List[InputPrompt]:
        """Return list of inputs needed from user during init workflow"""
        pass
    
    @abstractmethod
    async def render(self, context: 'ContextSnapshot') -> AdapterOutput:
        """Generate manifests and capability data from configuration"""
        pass
    
    @abstractmethod
    def pre_work_scripts(self) -> List[ScriptReference]:
        """Scripts to run before adapter bootstrap (e.g., rescue mode)"""
        pass
    
    @abstractmethod
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """Core adapter responsibility scripts (e.g., install OS, wait for CNI)"""
        pass
    
    @abstractmethod
    def post_work_scripts(self) -> List[ScriptReference]:
        """Scripts to run after adapter bootstrap (e.g., additional config)"""
        pass
    
    @abstractmethod
    def validation_scripts(self) -> List[ScriptReference]:
        """Scripts to validate deployment success"""
        pass
```

### Adapter Metadata (adapter.yaml)

```yaml
name: talos
display_name: Talos Linux
version: 1.0.0
phase: os
selection_group: operating_system
is_default: true

capabilities:
  provides:
    - kubernetes-api
  requires:
    - cloud-infrastructure
    - cni-artifacts

supported_versions:
  - v1.11.5
  - v1.11.4
  - v1.10.6

default_version: v1.11.5

description: |
  Talos Linux is an immutable Kubernetes OS designed for security and simplicity.
  Provides bare-metal Kubernetes cluster bootstrapping.
```