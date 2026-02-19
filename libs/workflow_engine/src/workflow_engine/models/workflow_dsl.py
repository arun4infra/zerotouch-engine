"""Workflow DSL Pydantic models"""
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any, Literal
from .validation import ValidationRules


class QuestionNode(BaseModel):
    """Workflow question definition"""
    id: str = Field(..., description="Unique question identifier")
    type: Literal["string", "integer", "boolean", "choice"] = Field(..., description="Question type")
    prompt: str = Field(..., description="Question prompt text")
    help_text: Optional[str] = Field(None, description="Help text for question")
    default: Optional[Any] = Field(None, description="Default answer value")
    validation: Optional[ValidationRules] = Field(None, description="Validation rules")
    automatic_answer: Optional[str] = Field(None, description="Automatic answer expression")
    sensitive: bool = Field(False, description="Whether field contains sensitive data")
    
    class Config:
        frozen = True


class TransitionNode(BaseModel):
    """Workflow state transition definition"""
    from_state: str = Field(..., description="Source state ID")
    to_state: str = Field(..., description="Target state ID")
    condition: Optional[str] = Field(None, description="Transition condition expression")
    
    class Config:
        frozen = True


class StateNode(BaseModel):
    """Workflow state definition"""
    question: QuestionNode = Field(..., description="Question for this state")
    next_state: Optional[str] = Field(None, description="Next state ID")
    
    class Config:
        frozen = True


class WorkflowDSL(BaseModel):
    """Complete workflow definition"""
    version: str = Field(..., description="Workflow DSL version")
    workflow_id: str = Field(..., description="Unique workflow identifier")
    states: Dict[str, StateNode] = Field(..., description="Workflow states")
    transitions: List[TransitionNode] = Field(default_factory=list, description="State transitions")
    
    @validator('version')
    def validate_version(cls, v):
        """Validate workflow DSL version"""
        if v not in ["1.0.0"]:
            raise ValueError(f"Unsupported workflow DSL version: {v}")
        return v
    
    @validator('states')
    def validate_unique_state_ids(cls, v):
        """Validate state IDs are unique"""
        state_ids = list(v.keys())
        if len(state_ids) != len(set(state_ids)):
            raise ValueError("Duplicate state IDs found in workflow")
        return v
    
    class Config:
        frozen = True
