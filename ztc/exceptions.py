"""ZTC Exception Classes

Base exception hierarchy for ZeroTouch Composition Engine.
All custom exceptions include help_text for actionable user guidance.
"""

from typing import List, Optional


class ZTCError(Exception):
    """Base exception for all ZTC errors
    
    All ZTC exceptions should inherit from this class to enable
    consistent error handling and user-friendly error messages.
    
    Attributes:
        message: Human-readable error description
        help_text: Optional actionable guidance for resolving the error
    """
    
    def __init__(self, message: str, help_text: str = None):
        """Initialize ZTC error with message and optional help text
        
        Args:
            message: Error description
            help_text: Optional remediation guidance
        """
        self.message = message
        self.help_text = help_text
        super().__init__(message)
    
    def __str__(self) -> str:
        """Format error message with help text if available"""
        if self.help_text:
            return f"{self.message}\n\nHelp: {self.help_text}"
        return self.message


class MissingCapabilityError(ZTCError):
    """Raised when an adapter requires a capability that no adapter provides
    
    This error occurs during dependency resolution when an adapter declares
    a required capability but no other adapter in the configuration provides it.
    """
    
    def __init__(
        self,
        adapter_name: str,
        capability: str,
        available_adapters: Optional[List[str]] = None
    ):
        """Initialize missing capability error
        
        Args:
            adapter_name: Name of adapter requiring the capability
            capability: Missing capability identifier
            available_adapters: List of adapters that could provide this capability
        """
        message = (
            f"Adapter '{adapter_name}' requires capability '{capability}' "
            f"but no adapter provides it"
        )
        
        help_text = f"Add an adapter that provides '{capability}' capability to platform.yaml"
        
        if available_adapters:
            help_text += f"\n\nAdapters that provide '{capability}':\n"
            help_text += "\n".join(f"  - {adapter}" for adapter in available_adapters)
            help_text += f"\n\nRun 'ztc init' to add one of these adapters to your configuration"
        
        super().__init__(message, help_text)
        self.adapter_name = adapter_name
        self.capability = capability
        self.available_adapters = available_adapters



class LockFileValidationError(ZTCError):
    """Raised when lock file validation fails
    
    This error occurs when the lock file doesn't match the current state,
    indicating potential drift between rendered artifacts and configuration.
    """
    
    def __init__(
        self,
        reason: str,
        lock_file_path: Optional[str] = None,
        expected_value: Optional[str] = None,
        actual_value: Optional[str] = None
    ):
        """Initialize lock file validation error
        
        Args:
            reason: Description of validation failure
            lock_file_path: Path to the lock file
            expected_value: Expected value from lock file
            actual_value: Actual value found
        """
        message = f"Lock file validation failed: {reason}"
        
        help_text = "Run 'ztc render' to regenerate artifacts and update the lock file"
        
        if expected_value and actual_value:
            help_text += f"\n\nExpected: {expected_value}\nActual: {actual_value}"
        
        help_text += "\n\nThis error prevents drift between rendered artifacts and configuration."
        help_text += "\nIf you've intentionally modified platform.yaml, re-render to update artifacts."
        
        super().__init__(message, help_text)
        self.reason = reason
        self.lock_file_path = lock_file_path
        self.expected_value = expected_value
        self.actual_value = actual_value



class RuntimeDependencyError(ZTCError):
    """Raised when required runtime dependencies are missing
    
    This error occurs when ZTC cannot find required external tools
    like jq, yq, kubectl, or talosctl that are needed for bootstrap execution.
    """
    
    def __init__(
        self,
        tool_name: str,
        required_for: Optional[str] = None,
        install_instructions: Optional[str] = None
    ):
        """Initialize runtime dependency error
        
        Args:
            tool_name: Name of the missing tool
            required_for: What operation requires this tool
            install_instructions: Optional installation guidance
        """
        message = f"Required tool '{tool_name}' not found in PATH"
        
        if required_for:
            message += f" (required for {required_for})"
        
        help_text = f"Install '{tool_name}' before running this command"
        
        if install_instructions:
            help_text += f"\n\n{install_instructions}"
        else:
            # Provide default installation hints for common tools
            install_hints = {
                "jq": "Install with: brew install jq (macOS) or apt-get install jq (Linux)",
                "yq": "Install with: brew install yq (macOS) or snap install yq (Linux)",
                "kubectl": "Install from: https://kubernetes.io/docs/tasks/tools/",
                "talosctl": "Install from: https://www.talos.dev/latest/introduction/getting-started/",
            }
            
            if tool_name in install_hints:
                help_text += f"\n\n{install_hints[tool_name]}"
        
        super().__init__(message, help_text)
        self.tool_name = tool_name
        self.required_for = required_for
