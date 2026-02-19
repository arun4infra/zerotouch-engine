"""Secret resolution for environment variable references"""
import os
from typing import Any, Dict


class SecretNotFoundError(Exception):
    """Raised when environment variable for secret is not found"""
    def __init__(self, env_var: str, field: str):
        self.env_var = env_var
        self.field = field
        super().__init__(f"Environment variable {env_var} not set for field {field}")


class SecretResolver:
    """Resolves environment variable references to actual secret values"""
    
    @staticmethod
    def is_secret_reference(value: Any) -> bool:
        """Check if value is an environment variable reference
        
        Args:
            value: Value to check
            
        Returns:
            True if value is a string starting with $
        """
        return isinstance(value, str) and value.startswith("$") and len(value) > 1
    
    @staticmethod
    def resolve_secret(reference: str, field: str = "unknown") -> str:
        """Resolve environment variable reference to actual value
        
        Args:
            reference: Environment variable reference (e.g., "$HETZNER_API_TOKEN")
            field: Field name for error reporting
            
        Returns:
            Resolved secret value from environment
            
        Raises:
            SecretNotFoundError: If environment variable is not set
        """
        if not SecretResolver.is_secret_reference(reference):
            return reference
        
        env_var = reference[1:]  # Remove $ prefix
        value = os.getenv(env_var)
        
        if value is None:
            raise SecretNotFoundError(env_var, field)
        
        return value
    
    @staticmethod
    def mask_sensitive_value(value: str) -> str:
        """Mask sensitive value for display/logging
        
        Args:
            value: Value to mask
            
        Returns:
            Masked string
        """
        return "***REDACTED***"
    
    @staticmethod
    def create_secret_reference(env_var_name: str) -> str:
        """Create environment variable reference from variable name
        
        Args:
            env_var_name: Environment variable name
            
        Returns:
            Reference string (e.g., "$HETZNER_API_TOKEN")
        """
        return f"${env_var_name}"
    
    @staticmethod
    def resolve_context_secrets(context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve all secret references in a context dictionary
        
        Args:
            context: Dictionary potentially containing secret references
            
        Returns:
            New dictionary with resolved secret values
            
        Raises:
            SecretNotFoundError: If any environment variable is not set
        """
        resolved = {}
        for key, value in context.items():
            if SecretResolver.is_secret_reference(value):
                resolved[key] = SecretResolver.resolve_secret(value, key)
            elif isinstance(value, dict):
                resolved[key] = SecretResolver.resolve_context_secrets(value)
            elif isinstance(value, list):
                resolved[key] = [
                    SecretResolver.resolve_secret(item, f"{key}[{i}]") 
                    if SecretResolver.is_secret_reference(item) 
                    else item
                    for i, item in enumerate(value)
                ]
            else:
                resolved[key] = value
        return resolved
