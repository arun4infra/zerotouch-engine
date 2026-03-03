"""Cluster API adapter configuration model."""

from pydantic import BaseModel, Field, model_validator
from typing import List


class WorkerPoolConfig(BaseModel):
    """Worker pool configuration."""
    name: str = Field(..., min_length=1)
    machine_type: str = Field(..., min_length=1)
    min_size: int = Field(..., ge=0)
    max_size: int = Field(..., ge=1)


class ControlPlaneConfig(BaseModel):
    """Control plane configuration."""
    machine_type: str = Field(..., min_length=1)
    replicas: int = Field(..., ge=1)


class ClusterAPIConfig(BaseModel):
    """Cluster API adapter configuration."""
    control_plane: ControlPlaneConfig = None
    worker_pools: List[WorkerPoolConfig] = Field(default_factory=list)
    
    # Flat fields for input collection
    control_plane_machine_type: str = None
    control_plane_replicas: int = None
    worker_pool_name: str = None
    worker_pool_machine_type: str = None
    worker_pool_min_size: int = None
    worker_pool_max_size: int = None
    
    @model_validator(mode='before')
    @classmethod
    def transform_flat_to_nested(cls, values):
        """Transform flat input fields to nested structure."""
        if isinstance(values, dict):
            # Build control_plane from flat fields
            if 'control_plane_machine_type' in values and 'control_plane_replicas' in values:
                values['control_plane'] = {
                    'machine_type': values.pop('control_plane_machine_type'),
                    'replicas': values.pop('control_plane_replicas')
                }
            
            # Build worker_pools from flat fields
            if all(k in values for k in ['worker_pool_name', 'worker_pool_machine_type', 
                                          'worker_pool_min_size', 'worker_pool_max_size']):
                values['worker_pools'] = [{
                    'name': values.pop('worker_pool_name'),
                    'machine_type': values.pop('worker_pool_machine_type'),
                    'min_size': values.pop('worker_pool_min_size'),
                    'max_size': values.pop('worker_pool_max_size')
                }]
        
        return values
