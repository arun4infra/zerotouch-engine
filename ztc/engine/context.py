"""Platform context management with immutable snapshots"""

from typing import Dict, Any
from pydantic import BaseModel

from ztc.interfaces.capabilities import CAPABILITY_CONTRACTS, Capability
from ztc.adapters.base import AdapterOutput


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
        """Initialize immutable context snapshot
        
        Args:
            capabilities: Capability registry (enum -> Pydantic model)
            outputs: Adapter outputs by name
        """
        self._capabilities = capabilities.copy()  # Shallow copy for immutability
        self._outputs = outputs.copy()
        self.environment = "production"
    
    def get_capability_data(self, capability: Capability) -> BaseModel:
        """Get strongly-typed capability data using enum (type-safe)
        
        Args:
            capability: Capability enum (e.g., Capability.CNI)
        
        Returns:
            Validated capability data as Pydantic model
        
        Raises:
            CapabilityNotFoundError: If capability not available
            TypeError: If capability data doesn't match expected type
        """
        # Handle both string and Enum capability names
        cap_key = capability.value if hasattr(capability, 'value') else capability
        
        if cap_key not in self._capabilities:
            raise CapabilityNotFoundError(
                f"No adapter provides capability '{cap_key}'"
            )
        
        capability_data = self._capabilities[cap_key]
        expected_type = CAPABILITY_CONTRACTS.get(cap_key)
        
        # Type safety check
        if not isinstance(capability_data, expected_type):
            raise TypeError(
                f"Capability '{capability.value}' expected type {expected_type.__name__}, "
                f"got {type(capability_data).__name__}"
            )
        
        return capability_data
    
    def has_capability(self, capability: Capability) -> bool:
        """Check if capability is available
        
        Args:
            capability: Capability enum to check
            
        Returns:
            True if capability is available, False otherwise
        """
        return capability in self._capabilities
    
    def get_output(self, adapter_name: str) -> AdapterOutput:
        """Get complete output from upstream adapter (legacy, use get_capability_data)
        
        Args:
            adapter_name: Name of adapter
            
        Returns:
            AdapterOutput from the adapter
            
        Raises:
            AdapterNotExecutedError: If adapter hasn't been executed yet
        """
        if adapter_name not in self._outputs:
            raise AdapterNotExecutedError(
                f"Adapter '{adapter_name}' has not been executed yet"
            )
        return self._outputs[adapter_name]



class PlatformContext:
    """Mutable context managed by Engine (not exposed to adapters)"""
    
    def __init__(self):
        """Initialize empty platform context"""
        self._outputs: Dict[str, AdapterOutput] = {}
        self._capabilities: Dict[Capability, BaseModel] = {}  # Enum-keyed registry
        self.environment = "production"
    
    def register_output(self, adapter_name: str, output: AdapterOutput):
        """Register adapter output and validate capability contracts
        
        Args:
            adapter_name: Name of the adapter
            output: AdapterOutput from the adapter
            
        Raises:
            ValueError: If capability is unknown
            TypeError: If capability data doesn't match contract
            CapabilityConflictError: If capability already provided
        """
        self._outputs[adapter_name] = output
        
        # Register and validate capabilities
        for capability_str, capability_data in output.capabilities.items():
            # Convert string to enum
            try:
                capability = Capability(capability_str)
            except ValueError:
                raise ValueError(
                    f"Adapter '{adapter_name}' provides unknown capability '{capability_str}'. "
                    f"Valid capabilities: {[c.value for c in Capability]}"
                )
            
            # Enforce Pydantic model requirement
            if not isinstance(capability_data, BaseModel):
                raise TypeError(
                    f"Adapter '{adapter_name}' capability '{capability.value}' must be a Pydantic model, "
                    f"got {type(capability_data).__name__}"
                )
            
            # Validate against registered contract
            expected_type = CAPABILITY_CONTRACTS[capability]
            if not isinstance(capability_data, expected_type):
                raise TypeError(
                    f"Adapter '{adapter_name}' capability '{capability.value}' must be {expected_type.__name__}, "
                    f"got {type(capability_data).__name__}"
                )
            
            # Check for conflicts
            if capability in self._capabilities:
                raise CapabilityConflictError(
                    f"Capability '{capability.value}' already provided by another adapter"
                )
            
            self._capabilities[capability] = capability_data
    
    def snapshot(self) -> ContextSnapshot:
        """Create immutable snapshot for adapter consumption
        
        Returns:
            ContextSnapshot with current capabilities and outputs
        """
        return ContextSnapshot(
            capabilities=self._capabilities,
            outputs=self._outputs
        )
    
    def has_capability(self, capability: Capability) -> bool:
        """Check if capability is available
        
        Args:
            capability: Capability enum to check
            
        Returns:
            True if capability is available, False otherwise
        """
        return capability in self._capabilities
    
    def get_capability_data(self, capability: Capability) -> BaseModel:
        """Get strongly-typed capability data (for testing/engine internal use)
        
        Args:
            capability: Capability enum or string
        
        Returns:
            Validated capability data as Pydantic model
        
        Raises:
            CapabilityNotFoundError: If capability not available
        """
        # Handle both string and Enum capability names
        cap_key = capability.value if hasattr(capability, 'value') else capability
        
        if cap_key not in self._capabilities:
            raise CapabilityNotFoundError(
                f"No adapter provides capability '{cap_key}'"
            )
        
        return self._capabilities[cap_key]
    
    def get_output(self, adapter_name: str) -> AdapterOutput:
        """Get adapter output (for engine internal use)
        
        Args:
            adapter_name: Name of adapter
            
        Returns:
            AdapterOutput from the adapter
            
        Raises:
            AdapterNotExecutedError: If adapter hasn't been executed yet
        """
        if adapter_name not in self._outputs:
            raise AdapterNotExecutedError(
                f"Adapter '{adapter_name}' has not been executed yet"
            )
        return self._outputs[adapter_name]
