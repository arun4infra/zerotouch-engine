"""Prerequisite checker for init workflow."""

from pathlib import Path
from typing import List

from ..models.prerequisite_result import PrerequisiteResult
from ..services.platform_config_service import PlatformConfigService


class PrerequisiteChecker:
    """Checks prerequisites for init workflow.
    
    Validates that:
    - platform.yaml does not already exist
    - Required directories can be created
    """

    def __init__(self, config_service: PlatformConfigService):
        """Initialize checker with config service.
        
        Args:
            config_service: Service for checking platform.yaml existence
        """
        self.config_service = config_service

    def check(self) -> PrerequisiteResult:
        """Check if init can run.
        
        Validates:
        1. platform.yaml does not exist (prevents re-initialization)
        2. Required directories (.zerotouch-cache, platform) can be created
        
        Returns:
            PrerequisiteResult with success status and error details if failed
        """
        # Check if platform.yaml exists
        if self.config_service.exists():
            return PrerequisiteResult(
                success=False,
                error="Platform configuration already exists",
                message="Delete platform.yaml to reconfigure"
            )

        # Check if required directories can be created
        required_dirs: List[Path] = [
            Path(".zerotouch-cache"),
            Path("platform")
        ]

        for dir_path in required_dirs:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return PrerequisiteResult(
                    success=False,
                    error=f"Cannot create directory: {dir_path}",
                    message=str(e)
                )

        return PrerequisiteResult(success=True)
