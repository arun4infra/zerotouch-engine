"""GitHub adapter for Git provider configuration"""

from typing import List, Type, Dict, Any
from pathlib import Path
from enum import Enum
import yaml

from ztc.adapters.base import (
    PlatformAdapter,
    InputPrompt,
    ScriptReference,
    AdapterOutput,
)
from .config import GitHubConfig


class GitHubScripts(str, Enum):
    """Script resource paths (validated at class load)"""
    VALIDATE_ACCESS = "init/validate-github-access.sh"
    INJECT_IDENTITIES = "bootstrap/00-inject-identities.sh"
    ENV_SUBSTITUTION = "bootstrap/apply-env-substitution.sh"
    VALIDATE_CREDENTIALS = "validation/validate-github-credentials.sh"


class GithubAdapter(PlatformAdapter):
    """GitHub Git provider adapter"""
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata from GitHub adapter directory"""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        return yaml.safe_load(metadata_path.read_text())
    
    @property
    def config_model(self) -> Type[GitHubConfig]:
        return GitHubConfig
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Interactive prompts for ztc init"""
        return [
            InputPrompt(
                name="github_app_id",
                prompt="GitHub App ID",
                type="string",
                validation=r"^\d+$",
                help_text="GitHub App ID (numbers only)"
            ),
            InputPrompt(
                name="github_app_installation_id",
                prompt="GitHub App Installation ID",
                type="string",
                validation=r"^\d+$",
                help_text="Installation ID for your organization"
            ),
            InputPrompt(
                name="github_app_private_key",
                prompt="GitHub App Private Key",
                type="password",
                validation=r"^-----BEGIN RSA PRIVATE KEY-----[\s\S]+-----END RSA PRIVATE KEY-----$",
                help_text="Loaded from .env.global (GIT_APP_PRIVATE_KEY)"
            ),
            InputPrompt(
                name="tenant_repo_url",
                prompt="Tenant Repository URL",
                type="string",
                validation=r"^https://github\.com/[^/]+/[^/]+/?$",
                help_text="Format: https://github.com/org/repo"
            )
        ]
    
    def init(self) -> List[ScriptReference]:
        """Return init-phase scripts for GitHub API validation"""
        config = GitHubConfig(**self.config)
        
        # Extract org and repo from URL
        import re
        match = re.match(r"^https://github\.com/([^/]+)/([^/]+)/?$", config.tenant_repo_url.rstrip('/'))
        tenant_org = match.group(1)
        tenant_repo = match.group(2)
        
        return [
            ScriptReference(
                package="ztc.adapters.github.scripts",
                resource=GitHubScripts.VALIDATE_ACCESS,
                description="Validate GitHub API access to tenant repository",
                timeout=60,
                context_data={
                    "github_app_id": config.github_app_id,
                    "github_app_installation_id": config.github_app_installation_id,
                    "tenant_org": tenant_org,
                    "tenant_repo": tenant_repo
                },
                secret_env_vars={
                    "GITHUB_APP_PRIVATE_KEY": config.github_app_private_key.get_secret_value()
                }
            )
        ]
    
    def pre_work_scripts(self) -> List[ScriptReference]:
        """GitHub adapter has no pre-work scripts"""
        return []
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """Return bootstrap scripts for GitHub credential injection and env substitution"""
        config = GitHubConfig(**self.config)
        
        # Extract org and repo from URL
        import re
        match = re.match(r"^https://github\.com/([^/]+)/([^/]+)/?$", config.tenant_repo_url.rstrip('/'))
        tenant_org = match.group(1)
        tenant_repo = match.group(2)
        
        return [
            ScriptReference(
                package="ztc.adapters.github.scripts",
                resource=GitHubScripts.INJECT_IDENTITIES,
                description="Inject GitHub App credentials into ArgoCD namespace",
                timeout=30,
                context_data={
                    "github_app_id": config.github_app_id,
                    "github_app_installation_id": config.github_app_installation_id
                },
                secret_env_vars={
                    "GITHUB_APP_PRIVATE_KEY": config.github_app_private_key.get_secret_value()
                }
            ),
            ScriptReference(
                package="ztc.adapters.github.scripts",
                resource=GitHubScripts.ENV_SUBSTITUTION,
                description="Substitute tenant repo URLs in ArgoCD manifests",
                timeout=30,
                context_data={
                    "tenant_org_name": tenant_org,
                    "tenant_repo_name": tenant_repo
                }
            )
        ]
    
    def post_work_scripts(self) -> List[ScriptReference]:
        """GitHub adapter has no post-work scripts"""
        return []
    
    def validation_scripts(self) -> List[ScriptReference]:
        """Return validation scripts to verify GitHub credentials in cluster"""
        config = GitHubConfig(**self.config)
        
        return [
            ScriptReference(
                package="ztc.adapters.github.scripts",
                resource=GitHubScripts.VALIDATE_CREDENTIALS,
                description="Validate GitHub App credentials in cluster",
                timeout=30,
                context_data={
                    "tenant_org": config.tenant_org_name,
                    "tenant_repo": f"{config.tenant_repo_name}-tenants"
                }
            )
        ]
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate GitHub adapter output (no manifests)"""
        config = GitHubConfig(**self.config)
        
        # GitHub adapter provides capability data but no manifests
        # Capability data will be used by other adapters (e.g., ArgoCD)
        capability_data = {
            "git-credentials": {
                "provider": "github",
                "app_id": config.github_app_id,
                "installation_id": config.github_app_installation_id,
                "tenant_org": config.tenant_org_name,
                "tenant_repo": config.tenant_repo_name
            }
        }
        
        return AdapterOutput(
            manifests={},  # No manifests generated
            stages=[],
            env_vars={},
            capabilities=capability_data,
            data={}
        )
