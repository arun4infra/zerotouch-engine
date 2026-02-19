"""Workflow result models."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Any

from workflow_engine.models.validation_result import ScriptResult


@dataclass
class WorkflowResult:
    """Result from workflow operation."""
    
    question: Optional[dict] = None
    state: Optional[dict] = None
    completed: bool = False
    error: Optional[str] = None
    validation_results: Optional[List[ScriptResult]] = None
    platform_yaml_path: Optional[Path] = None
    auto_answer: bool = False  # Engine signals CLI to auto-apply answer
    display_hint: Optional[str] = None  # Hints: "adapter_header", "validation_error"
