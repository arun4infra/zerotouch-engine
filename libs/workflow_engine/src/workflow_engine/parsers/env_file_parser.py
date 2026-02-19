"""Parser for .env files."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ValidationResult:
    """Result of environment variable validation."""
    success: bool
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class EnvFileParser:
    """Parser for .env files with support for comments, empty lines, and quoted values."""

    def parse(self, file_path: Path) -> Dict[str, str]:
        """Parse .env file into dictionary.
        
        Args:
            file_path: Path to .env file
            
        Returns:
            Dictionary of environment variables (KEY -> value)
            
        Handles:
            - Comments (lines starting with #)
            - Empty lines
            - Quoted values (single and double quotes)
            - KEY=VALUE format
        """
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

    def validate(self, env_vars: Dict[str, str]) -> ValidationResult:
        """Validate environment variable formats.
        
        Args:
            env_vars: Dictionary of environment variables to validate
            
        Returns:
            ValidationResult with success status and any error messages
            
        Validation rules:
            - Keys must be uppercase
            - Keys must contain only alphanumeric characters and underscores
            - Values must not be empty
        """
        errors = []
        
        for key, value in env_vars.items():
            # Check key format (uppercase, underscores)
            if not key.isupper() or not all(c.isalnum() or c == '_' for c in key):
                errors.append(f"Invalid key format: {key}")
            
            # Check non-empty values
            if not value:
                errors.append(f"Empty value for key: {key}")
        
        if errors:
            return ValidationResult(success=False, errors=errors)
        
        return ValidationResult(success=True)
