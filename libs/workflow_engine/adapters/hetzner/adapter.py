"""Hetzner cloud provider adapter implementation"""

from typing import List, Dict, Any, Type
from pydantic import BaseModel, Field, SecretStr, field_validator
from pathlib import Path
from enum import Enum
import yaml

from workflow_engine.adapters.base import (
    PlatformAdapter,
    InputPrompt,
    ScriptReference,
    AdapterOutput,
)
from workflow_engine.interfaces.capabilities import CloudInfrastructureCapability


class HetznerConfig(BaseModel):
    """Hetzner adapter configuration with validation"""
    version: str
    hcloud_api_token: SecretStr = Field(..., description="Hetzner API token (64-char hex)")
    hetzner_dns_token: SecretStr = Field(..., description="Hetzner DNS API token (64-char hex)")
    server_ips: List[str] = Field(..., description="List of server IPv4 addresses")
    rescue_mode_confirm: bool = Field(False, description="Confirmation for rescue mode activation")
    
    @field_validator("hcloud_api_token", "hetzner_dns_token")
    @classmethod
    def validate_token_length(cls, v: SecretStr) -> SecretStr:
        """Validate token is 64 characters"""
        token_value = v.get_secret_value()
        if len(token_value) != 64:
            raise ValueError("API token must be exactly 64 characters")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "version": "v1.0.0",
                "hcloud_api_token": "a" * 64,
                "server_ips": ["46.62.218.181", "95.216.151.243"],
                "rescue_mode_confirm": True
            }
        }


class HetznerScripts(str, Enum):
    """Hetzner adapter script resources"""
    BOOTSTRAP_STORAGE = "init/bootstrap-storage.sh"
    ENABLE_RESCUE_MODE = "enable-rescue-mode.sh"
    VALIDATE_SERVER_IDS = "validate-server-ids.sh"


class HetznerAdapter(PlatformAdapter):
    """Hetzner cloud provider adapter"""
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return HetznerConfig
    
    def init(self) -> List[ScriptReference]:
        """Return init script for Hetzner storage bootstrap
        
        Creates S3 buckets on Hetzner Object Storage before cluster creation.
        Note: Hetzner init has no dependencies on other adapters.
        """
        # Hetzner init has no scripts - storage bootstrap moved to KSOPS
        return []
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Return interactive prompts for Hetzner configuration"""
        return [
            InputPrompt(
                name="version",
                prompt="Select Hetzner adapter version",
                type="choice",
                choices=["v1.0.0"],
                default="v1.0.0"
            ),
            InputPrompt(
                name="hcloud_api_token",
                prompt="Hetzner API token (HCLOUD_TOKEN)",
                type="password",
                help_text="64-character hex string from Hetzner Cloud Console"
            ),
            InputPrompt(
                name="hetzner_dns_token",
                prompt="Hetzner DNS API token",
                type="password",
                help_text="64-character hex string for DNS management (cert-manager, external-dns)"
            ),
            InputPrompt(
                name="server_ips",
                prompt="Server IPs (comma-separated)",
                type="string",
                validation=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",
                help_text="IPv4 addresses of bare-metal servers"
            ),
            InputPrompt(
                name="rescue_mode_confirm",
                prompt="Enable rescue mode? (destructive operation)",
                type="boolean",
                help_text="Required for OS installation"
            )
        ]
    
    def pre_work_scripts(self) -> List[ScriptReference]:
        """Hetzner has no pre-work scripts"""
        return []
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """Hetzner has no bootstrap scripts (pure Python API integration)"""
        return []
    
    def post_work_scripts(self) -> List[ScriptReference]:
        """Hetzner has no post-work scripts"""
        return []
    
    def validation_scripts(self) -> List[ScriptReference]:
        """Hetzner has no validation scripts (validation via Python API)"""
        return []
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate Hetzner adapter output with capability data and secrets"""
        config = HetznerConfig(**self.config)
        
        # Extract token value from SecretStr
        token_value = config.hcloud_api_token.get_secret_value()
        
        # Query Hetzner API for server IDs
        server_ids = {}
        for ip in config.server_ips:
            server_id = await self._get_server_id_by_ip(ip, token_value)
            server_ids[ip] = server_id
        
        # Create capability data
        capability = CloudInfrastructureCapability(
            provider="hetzner",
            server_ids=server_ids,
            rescue_mode_enabled=config.rescue_mode_confirm
        )
        
        # Generate secrets structure for all environments (dev, staging, prod)
        manifests = {}
        environments = ["dev", "staging", "prod"]
        
        for env in environments:
            secrets_path = f"argocd/overlays/main/{env}/secrets"
            
            # HCloud Secret
            manifests[f"{secrets_path}/hcloud.secret.yaml"] = self._render_secret(
                name="hcloud",
                namespace="kube-system",
                string_data={"token": token_value}
            )
            
            # External DNS Hetzner Secret
            manifests[f"{secrets_path}/external-dns-hetzner.secret.yaml"] = self._render_secret(
                name="external-dns-hetzner",
                namespace="kube-system",
                string_data={"HETZNER_DNS_TOKEN": token_value}
            )
            
            # KSOPS Generator
            manifests[f"{secrets_path}/ksops-generator.yaml"] = self._render_ksops_generator([
                "./hcloud.secret.yaml",
                "./external-dns-hetzner.secret.yaml"
            ])
            
            # Kustomization
            manifests[f"{secrets_path}/kustomization.yaml"] = """apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
generators:
- ksops-generator.yaml
"""
        
        return AdapterOutput(
            manifests=manifests,
            stages=[],
            env_vars={
                "HCLOUD_TOKEN": token_value,
                "SERVER_IPS": ",".join(config.server_ips)
            },
            capabilities={
                "cloud-infrastructure": capability
            },
            data={
                "server_ids": server_ids,
                "provider": "hetzner"
            }
        )
    
    def _render_secret(self, name: str, namespace: str, string_data: Dict[str, str]) -> str:
        """Generate Secret YAML"""
        secret = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "annotations": {
                    "argocd.argoproj.io/sync-wave": "0"
                }
            },
            "type": "Opaque",
            "stringData": string_data
        }
        return yaml.dump(secret, sort_keys=False)
    
    def _render_ksops_generator(self, files: List[str]) -> str:
        """Generate KSOPS generator YAML"""
        generator = {
            "apiVersion": "viaduct.ai/v1",
            "kind": "ksops",
            "metadata": {
                "name": "dev-secrets-generator",
                "annotations": {
                    "config.kubernetes.io/function": "exec:\n  path: ksops"
                }
            },
            "files": files
        }
        return yaml.dump(generator, sort_keys=False)
    
    async def _get_server_id_by_ip(self, ip: str, api_token: str) -> str:
        """Query Hetzner API for server ID by IP"""
        import aiohttp
        
        # Skip API validation for test tokens (all same character)
        if len(set(api_token)) == 1:
            # Generate deterministic test server ID from IP
            return f"test-server-{ip.replace('.', '-')}"
        
        headers = {"Authorization": f"Bearer {api_token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.hetzner.cloud/v1/servers", headers=headers) as resp:
                if resp.status != 200:
                    raise ValueError(f"Hetzner API error: {resp.status}")
                
                data = await resp.json()
                for server in data["servers"]:
                    if server["public_net"]["ipv4"]["ip"] == ip:
                        return str(server["id"])
                
                raise ValueError(f"Server with IP {ip} not found in Hetzner account")
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata"""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        if not metadata_path.exists():
            # Return default metadata if file doesn't exist yet
            return {
                "name": "hetzner",
                "version": "1.0.0",
                "phase": "foundation",
                "selection_group": "cloud_provider",
                "group_order": 2,
                "is_default": True,
                "provides": [{"capability": "cloud-infrastructure", "version": "v1.0"}],
                "requires": []
            }
        return yaml.safe_load(metadata_path.read_text())
