"""Validation result models for adapter validation"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ScriptResult:
    """Result from script execution"""
    description: str
    success: bool
    exit_code: int
    stdout: str
    stderr: str


@dataclass
class ValidationResult:
    """Result from validation"""
    success: bool
    scripts: List[ScriptResult] = field(default_factory=list)
    error: Optional[str] = None
    stderr: Optional[str] = None
