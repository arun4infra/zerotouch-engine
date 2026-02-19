"""Platform context management with immutable snapshots"""

from typing import Dict, Any
from pydantic import BaseModel

from workflow_engine.interfaces.capabilities import CAPABILITY_CONTRACTS, Capability
from workflow_engine.adapters.base import AdapterOutput


class CapabilityNotFoundError(Exception):
    """Raised when requested capability is not available"""
    pass


class AdapterNotExecutedError(Exception):
    """Raised when adapter output is requested before execution"""
    pass


class CapabilityConflictError(Exception):
    """Raised when multiple adapters provide the same capability"""
    pass


class ContextSnapshot:
    """Immutable snapshot of platform context (read-only for adapters)"""
    
    def __init__(self, capabilities: Dict[Capability, BaseModel], outputs: Dict[str, AdapterOutput]):
        self._capabilities = capabilities.copy()
        self._outputs = outputs.copy()
        self.environment = "production"
    
    def get_capability_data(self, capability: Capability) -> BaseModel:
        cap_key = capability.value if hasattr(capability, 'value') else capability
        if cap_key not in self._capabilities:
            raise CapabilityNotFoundError(f"No adapter provides capability '{cap_key}'")
        capability_data = self._capabilities[cap_key]
        expected_type = CAPABILITY_CONTRACTS.get(cap_key)
        if not isinstance(capability_data, expected_type):
            raise TypeError(f"Capability '{capability.value}' expected type {expected_type.__name__}, got {type(capability_data).__name__}")
        return capability_data
    
    def has_capability(self, capability: Capability) -> bool:
        return capability in self._capabilities
    
    def get_output(self, adapter_name: str) -> AdapterOutput:
        if adapter_name not in self._outputs:
            raise AdapterNotExecutedError(f"Adapter '{adapter_name}' has not been executed yet")
        return self._outputs[adapter_name]


class PlatformContext:
    """Mutable context managed by Engine (not exposed to adapters)"""
    
    def __init__(self):
        self._outputs: Dict[str, AdapterOutput] = {}
        self._capabilities: Dict[Capability, BaseModel] = {}
        self.environment = "production"
    
    def register_output(self, adapter_name: str, output: AdapterOutput):
        self._outputs[adapter_name] = output
        for capability_str, capability_data in output.capabilities.items():
            try:
                capability = Capability(capability_str)
            except ValueError:
                raise ValueError(f"Adapter '{adapter_name}' provides unknown capability '{capability_str}'. Valid capabilities: {[c.value for c in Capability]}")
            if not isinstance(capability_data, BaseModel):
                raise TypeError(f"Adapter '{adapter_name}' capability '{capability.value}' must be a Pydantic model, got {type(capability_data).__name__}")
            expected_type = CAPABILITY_CONTRACTS[capability]
            if not isinstance(capability_data, expected_type):
                raise TypeError(f"Adapter '{adapter_name}' capability '{capability.value}' must be {expected_type.__name__}, got {type(capability_data).__name__}")
            if capability in self._capabilities:
                raise CapabilityConflictError(f"Capability '{capability.value}' already provided by another adapter")
            self._capabilities[capability] = capability_data
    
    def snapshot(self) -> ContextSnapshot:
        return ContextSnapshot(capabilities=self._capabilities, outputs=self._outputs)
    
    def has_capability(self, capability: Capability) -> bool:
        return capability in self._capabilities
    
    def get_capability_data(self, capability: Capability) -> BaseModel:
        cap_key = capability.value if hasattr(capability, 'value') else capability
        if cap_key not in self._capabilities:
            raise CapabilityNotFoundError(f"No adapter provides capability '{cap_key}'")
        return self._capabilities[cap_key]
    
    def get_output(self, adapter_name: str) -> AdapterOutput:
        if adapter_name not in self._outputs:
            raise AdapterNotExecutedError(f"Adapter '{adapter_name}' has not been executed yet")
        return self._outputs[adapter_name]
