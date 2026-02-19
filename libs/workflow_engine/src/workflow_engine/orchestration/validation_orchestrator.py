"""Validation orchestrator for executing adapter validation scripts"""

from typing import TYPE_CHECKING
from workflow_engine.models.validation_result import ValidationResult, ScriptResult
from workflow_engine.engine.script_executor import ScriptExecutor

if TYPE_CHECKING:
    from workflow_engine.adapters.base import PlatformAdapter


class ValidationOrchestrator:
    """Orchestrates adapter validation by executing init scripts"""
    
    def __init__(self, script_executor: ScriptExecutor = None):
        self.script_executor = script_executor or ScriptExecutor()
    
    def validate_adapter(
        self,
        adapter: 'PlatformAdapter',
        config: dict
    ) -> ValidationResult:
        """Execute all validation scripts for adapter
        
        Args:
            adapter: The adapter to validate
            config: Adapter configuration
            
        Returns:
            ValidationResult with success status and script results
        """
        init_scripts = adapter.init() if hasattr(adapter, 'init') else []
        
        if not init_scripts:
            return ValidationResult(success=True, scripts=[])
        
        script_results = []
        for script_ref in init_scripts:
            result = self.script_executor.execute(script_ref)
            
            script_results.append(ScriptResult(
                description=script_ref.description,
                success=result.exit_code == 0,
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr
            ))
            
            if result.exit_code != 0:
                return ValidationResult(
                    success=False,
                    scripts=script_results,
                    error=f"{script_ref.description} failed",
                    stderr=result.stderr
                )
        
        return ValidationResult(success=True, scripts=script_results)
