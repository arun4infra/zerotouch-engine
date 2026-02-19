"""Validation service wrapper."""

from workflow_engine.orchestration.validation_orchestrator import ValidationOrchestrator
from workflow_engine.models.validation_result import ValidationResult


class ValidationService:
    """Service for validation coordination."""
    
    def __init__(self, orchestrator: ValidationOrchestrator = None):
        self.orchestrator = orchestrator or ValidationOrchestrator()
    
    def validate(self, adapter, config: dict) -> ValidationResult:
        """Validate adapter configuration."""
        return self.orchestrator.validate_adapter(adapter, config)
