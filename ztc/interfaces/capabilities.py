"""Capability interface contracts with type-safe enum-based lookups"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Type
from enum import StrEnum


class CNIArtifacts(BaseModel):
    """Strict contract for 'cni' capability providers (Cilium, Calico, etc.)"""
    manifests: str = Field(..., description="YAML manifests for CNI installation")
    cni_conf: Optional[str] = Field(None, description="CNI configuration file content")
    ready: bool = Field(False, description="Whether CNI is operational")


class KubernetesAPICapability(BaseModel):
    """Strict contract for 'kubernetes-api' capability providers (Talos, kubeadm, etc.)"""
    cluster_endpoint: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$")
    kubeconfig_path: str
    version: str = Field(..., pattern=r"^>=\d+\.\d+$")


class CloudInfrastructureCapability(BaseModel):
    """Strict contract for 'cloud-infrastructure' capability providers (Hetzner, AWS, etc.)"""
    provider: str
    server_ids: Dict[str, str]  # IP -> Server ID mapping
    rescue_mode_enabled: bool


class GatewayAPICapability(BaseModel):
    """Strict contract for 'gateway-api' capability providers"""
    version: str
    crds_embedded: bool


class Capability(StrEnum):
    """Type-safe capability identifiers (prevents typos like 'CNI' vs 'cni')"""
    CNI = "cni"
    KUBERNETES_API = "kubernetes-api"
    CLOUD_INFRASTRUCTURE = "cloud-infrastructure"
    GATEWAY_API = "gateway-api"


# Bind capability enums to Pydantic models
CAPABILITY_CONTRACTS: Dict[Capability, Type[BaseModel]] = {
    Capability.CNI: CNIArtifacts,
    Capability.KUBERNETES_API: KubernetesAPICapability,
    Capability.CLOUD_INFRASTRUCTURE: CloudInfrastructureCapability,
    Capability.GATEWAY_API: GatewayAPICapability,
}
