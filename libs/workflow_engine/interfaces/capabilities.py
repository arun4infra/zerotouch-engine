"""Capability interface contracts"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Type
from enum import StrEnum


class CNIArtifacts(BaseModel):
    manifests: str = Field(..., description="YAML manifests for CNI installation")
    cni_conf: Optional[str] = Field(None, description="CNI configuration file content")
    ready: bool = Field(False, description="Whether CNI is operational")


class KubernetesAPICapability(BaseModel):
    cluster_endpoint: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$")
    kubeconfig_path: str
    version: str = Field(..., pattern=r"^>=\d+\.\d+$")


class CloudInfrastructureCapability(BaseModel):
    provider: str
    server_ids: Dict[str, str]
    rescue_mode_enabled: bool


class GatewayAPICapability(BaseModel):
    version: str
    crds_embedded: bool


class SecretsManagementCapability(BaseModel):
    provider: str = Field(..., description="Secrets management provider name")
    s3_bucket: str = Field(..., description="S3 bucket for key backups")
    sops_config_path: str = Field(..., description="Path to .sops.yaml configuration")
    age_public_key: str = Field(..., description="Age public key for encryption")
    
    @property
    def encryption_env(self) -> Dict[str, str]:
        return {"SOPS_AGE_RECIPIENTS": self.age_public_key}


class InfrastructureProvisioningCapability(BaseModel):
    operator_version: str = Field(..., description="Infrastructure operator version")
    namespace: str = Field(..., description="Kubernetes namespace")
    installed_providers: list[str] = Field(..., description="List of installed providers")
    crds_ready: bool = Field(..., description="Whether provider CRDs are established")


class Capability(StrEnum):
    CNI = "cni"
    KUBERNETES_API = "kubernetes-api"
    CLOUD_INFRASTRUCTURE = "cloud-infrastructure"
    GATEWAY_API = "gateway-api"
    SECRETS_MANAGEMENT = "secrets-management"
    INFRASTRUCTURE_PROVISIONING = "infrastructure-provisioning"


CAPABILITY_CONTRACTS: Dict[Capability, Type[BaseModel]] = {
    Capability.CNI: CNIArtifacts,
    Capability.KUBERNETES_API: KubernetesAPICapability,
    Capability.CLOUD_INFRASTRUCTURE: CloudInfrastructureCapability,
    Capability.GATEWAY_API: GatewayAPICapability,
    Capability.SECRETS_MANAGEMENT: SecretsManagementCapability,
    Capability.INFRASTRUCTURE_PROVISIONING: InfrastructureProvisioningCapability,
}
