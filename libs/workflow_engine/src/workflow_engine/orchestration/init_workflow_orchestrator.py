"""Init workflow orchestrator."""

from pathlib import Path
from typing import Optional, Any

from workflow_engine.engine.init_workflow import InitWorkflow
from workflow_engine.registry.adapter_registry import AdapterRegistry
from workflow_engine.services.platform_config_service import PlatformConfigService
from workflow_engine.services.session_state_service import SessionStateService
from workflow_engine.orchestration.validation_orchestrator import ValidationOrchestrator
from workflow_engine.orchestration.prerequisite_checker import PrerequisiteChecker
from workflow_engine.models.workflow_result import WorkflowResult


class InitWorkflowOrchestrator:
    """Orchestrates init workflow with all business logic."""
    
    def __init__(
        self,
        config_service: Optional[PlatformConfigService] = None,
        session_service: Optional[SessionStateService] = None,
        validation_orchestrator: Optional[ValidationOrchestrator] = None,
        prerequisite_checker: Optional[PrerequisiteChecker] = None,
        registry: Optional[AdapterRegistry] = None
    ):
        from ..storage.session_store import FilesystemStore
        
        self.config_service = config_service or PlatformConfigService()
        self.session_service = session_service or SessionStateService(FilesystemStore())
        self.validation_orchestrator = validation_orchestrator or ValidationOrchestrator()
        self.prerequisite_checker = prerequisite_checker or PrerequisiteChecker(self.config_service)
        self.registry = registry or AdapterRegistry()
        self.workflow = InitWorkflow(self.registry)
    
    def check_prerequisites(self) -> bool:
        """Check if init can run."""
        result = self.prerequisite_checker.check()
        return result.success
    
    def start(self) -> WorkflowResult:
        """Start init workflow."""
        result = self.workflow.start()
        return WorkflowResult(
            question=result.get("question"),
            state=result.get("workflow_state"),
            completed=result.get("completed", False),
            error=result.get("error")
        )
    
    async def answer(self, state: dict, answer_value: Any) -> WorkflowResult:
        """Process answer and return next question."""
        # Process answer through workflow
        result = self.workflow.answer(state, answer_value)
        
        # Save org_name and app_name when collected
        if result.get("workflow_state"):
            answers = result["workflow_state"].get("answers", {})
            if "org_name" in answers and "app_name" in answers:
                # Update platform info
                if self.config_service.exists():
                    config = self.config_service.load()
                else:
                    from workflow_engine.models.platform_config import PlatformConfig, PlatformInfo
                    config = PlatformConfig(
                        version="1.0",
                        platform=PlatformInfo(organization="", app_name=""),
                        adapters={}
                    )
                
                config.platform.organization = answers["org_name"]
                config.platform.app_name = answers["app_name"]
                self.config_service.save(config)
        
        # If validation completed, save all validated adapters
        validated_adapters = result.get("validated_adapters", [])
        for adapter_info in validated_adapters:
            adapter_name = adapter_info["name"]
            adapter_config = adapter_info["config"]
            self.config_service.save_adapter(adapter_name, adapter_config)
        
        # Clear validated adapters from state after saving
        if validated_adapters and result.get("workflow_state"):
            result["workflow_state"]["validated_adapters"] = []
        
        # Save session state for crash recovery
        if not result.get("completed"):
            await self.session_service.save("init", result.get("workflow_state"))
        else:
            await self.session_service.delete("init")
        
        # Convert platform_yaml to path if present
        platform_yaml_path = None
        if result.get("completed") and result.get("platform_yaml"):
            platform_yaml_path = Path("platform/platform.yaml")
        
        return WorkflowResult(
            question=result.get("question"),
            state=result.get("workflow_state"),
            completed=result.get("completed", False),
            error=result.get("error"),
            validation_results=result.get("validation_scripts"),
            platform_yaml_path=platform_yaml_path,
            auto_answer=result.get("auto_answer", False),
            display_hint=result.get("display_hint")
        )
    
    def _extract_adapter_name(self, state: dict) -> Optional[str]:
        """Extract current adapter name from state."""
        if "current_adapter_inputs" in state:
            return state["current_adapter_inputs"].get("adapter_name")
        return None
    
    def _extract_adapter_config(self, state: dict, adapter_name: str) -> dict:
        """Extract adapter config from state."""
        if "current_adapter_inputs" in state:
            return state["current_adapter_inputs"].get("collected", {})
        
        # Fallback: search in answers
        for key, value in state.get("answers", {}).items():
            if key.endswith("_config") and isinstance(value, dict):
                return value
        
        return {}
