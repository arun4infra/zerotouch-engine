"""Validation rules for workflow questions"""
from pydantic import BaseModel, Field
from typing import Optional, List


class ValidationRules(BaseModel):
    """Validation rules for question answers"""
    regex: Optional[str] = Field(None, description="Regex pattern for string validation")
    min_value: Optional[int] = Field(None, description="Minimum value for integer validation")
    max_value: Optional[int] = Field(None, description="Maximum value for integer validation")
    choices: Optional[List[str]] = Field(None, description="Valid choices for choice validation")
    
    class Config:
        frozen = True
