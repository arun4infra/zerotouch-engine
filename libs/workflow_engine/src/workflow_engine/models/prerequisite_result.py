"""Prerequisite check result model"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class PrerequisiteResult:
    """Result from prerequisite check"""
    success: bool
    error: Optional[str] = None
    message: Optional[str] = None
