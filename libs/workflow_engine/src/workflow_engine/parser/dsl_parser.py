"""Workflow DSL parser with Pydantic validation and line number extraction"""
from pathlib import Path
from typing import Dict, Optional
import yaml
from ruamel.yaml import YAML
from pydantic import ValidationError

from ..models.workflow_dsl import WorkflowDSL


class WorkflowDSLError(Exception):
    """Workflow DSL parsing or validation error"""
    def __init__(self, message: str, line_number: Optional[int] = None):
        self.message = message
        self.line_number = line_number
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        """Format error message with line number if available"""
        if self.line_number:
            return f"{self.message} (line {self.line_number})"
        return self.message


class WorkflowDSLParser:
    """Parser for workflow DSL YAML files with validation"""
    
    def __init__(self):
        self.schema_cache: Dict[str, WorkflowDSL] = {}
        self._ruamel_yaml = YAML()
        self._ruamel_yaml.preserve_quotes = True
    
    async def parse_yaml(self, yaml_path: Path) -> WorkflowDSL:
        """Parse and validate YAML workflow
        
        Args:
            yaml_path: Path to workflow YAML file
            
        Returns:
            Validated WorkflowDSL instance
            
        Raises:
            WorkflowDSLError: If parsing or validation fails
        """
        # Check cache
        cache_key = str(yaml_path.resolve())
        if cache_key in self.schema_cache:
            return self.schema_cache[cache_key]
        
        # Load YAML data
        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            line_number = self._extract_yaml_error_line(e)
            raise WorkflowDSLError(
                f"YAML parsing error: {e}",
                line_number=line_number
            )
        except FileNotFoundError:
            raise WorkflowDSLError(f"Workflow file not found: {yaml_path}")
        except Exception as e:
            raise WorkflowDSLError(f"Error reading workflow file: {e}")
        
        # Validate with Pydantic
        try:
            workflow = WorkflowDSL(**data)
            self.schema_cache[cache_key] = workflow
            return workflow
        except ValidationError as e:
            line_number = await self._extract_line_number(yaml_path, e)
            raise WorkflowDSLError(
                f"Invalid workflow DSL: {self._format_validation_error(e)}",
                line_number=line_number
            )
    
    def _extract_yaml_error_line(self, error: yaml.YAMLError) -> Optional[int]:
        """Extract line number from YAML parsing error"""
        if hasattr(error, 'problem_mark'):
            return error.problem_mark.line + 1
        return None
    
    async def _extract_line_number(
        self, 
        yaml_path: Path, 
        error: ValidationError
    ) -> Optional[int]:
        """Extract line number from Pydantic validation error using ruamel.yaml
        
        Args:
            yaml_path: Path to YAML file
            error: Pydantic validation error
            
        Returns:
            Line number if found, None otherwise
        """
        try:
            # Get the field path from the first error
            if not error.errors():
                return None
            
            first_error = error.errors()[0]
            field_path = first_error.get('loc', ())
            
            if not field_path:
                return None
            
            # Load YAML with ruamel to get line numbers
            with open(yaml_path) as f:
                data = self._ruamel_yaml.load(f)
            
            # Navigate to the field location
            current = data
            for field in field_path:
                if isinstance(current, dict) and field in current:
                    current = current[field]
                elif isinstance(current, list) and isinstance(field, int):
                    if 0 <= field < len(current):
                        current = current[field]
                    else:
                        return None
                else:
                    return None
            
            # Extract line number from ruamel.yaml CommentedMap/CommentedSeq
            if hasattr(current, 'lc'):
                return current.lc.line + 1
            
            return None
        except Exception:
            # If line extraction fails, return None
            return None
    
    def _format_validation_error(self, error: ValidationError) -> str:
        """Format Pydantic validation error for user display
        
        Args:
            error: Pydantic validation error
            
        Returns:
            Formatted error message
        """
        errors = error.errors()
        if not errors:
            return str(error)
        
        # Format first error with field path
        first_error = errors[0]
        field_path = '.'.join(str(loc) for loc in first_error.get('loc', ()))
        message = first_error.get('msg', 'Validation failed')
        
        if field_path:
            return f"{field_path}: {message}"
        return message
    
    def clear_cache(self) -> None:
        """Clear the schema cache"""
        self.schema_cache.clear()
