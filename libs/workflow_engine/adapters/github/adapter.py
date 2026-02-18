"""GitHub adapter for Git provider configuration"""

from typing import List, Type, Dict, Any
from pathlib import Path
from enum import Enum
import yaml

from workflow_engine.adapters.base import (
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
                type="env_file",
                validation=r"^-----BEGIN RSA PRIVATE KEY-----[\s\S]+-----END RSA PRIVATE KEY-----$",
                help_text="Loaded from .env.global (GIT_APP_PRIVATE_KEY)"
            ),
            InputPrompt(
                name="control_plane_repo_url",
                prompt="Control Plane Repository URL (infrastructure/platform)",
                type="string",
                validation=r"^https://github\.com/[^/]+/[^/]+/?$",
                help_text="Format: https://github.com/org/repo"
            ),
            InputPrompt(
                name="data_plane_repo_url",
                prompt="Data Plane Repository URL (tenant/application configs)",
                type="string",
                validation=r"^https://github\.com/[^/]+/[^/]+/?$",
                help_text="Format: https://github.com/org/repo"
            )
        ]
    
    def collect_field_value(self, input_prompt: InputPrompt, current_config: Dict[str, Any]) -> Any:
        """Custom collection for GitHub-specific fields"""
        from rich.console import Console
        from rich.prompt import Confirm
        
        # Special handling for private key - load from .env.global
        if input_prompt.name == "github_app_private_key":
            console = Console()
            console.print("\n[yellow]GitHub App Private Key must be set in .env.global file[/yellow]")
            console.print("[dim]Add this line to .env.global:[/dim]")
            console.print('[dim]GIT_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\\n...\\n-----END RSA PRIVATE KEY-----"[/dim]')
            
            while True:
                ready = Confirm.ask("\nHave you added GIT_APP_PRIVATE_KEY to .env.global?")
                if not ready:
                    console.print("[yellow]Please add the key to .env.global and try again[/yellow]")
                    continue
                
                # Reload .env.global to get the key
                env_file = Path(".env.global")
                if not env_file.exists():
                    console.print("[red].env.global file not found[/red]")
                    continue
                
                # Parse .env.global for GIT_APP_PRIVATE_KEY (handles multi-line)
                key_value = None
                with open(env_file) as f:
                    content = f.read()
                    # Find GIT_APP_PRIVATE_KEY= and extract until closing quote
                    import re
                    match = re.search(r'GIT_APP_PRIVATE_KEY="(.*?)"', content, re.DOTALL)
                    if match:
                        key_value = match.group(1)
                
                if not key_value:
                    console.print("[red]GIT_APP_PRIVATE_KEY not found in .env.global[/red]")
                    continue
                
                # Validate the key format
                if not re.match(r"^-----BEGIN RSA PRIVATE KEY-----[\s\S]+-----END RSA PRIVATE KEY-----$", key_value, re.DOTALL):
                    console.print("[red]Invalid RSA private key format[/red]")
                    continue
                
                console.print("[green]✓[/green] Valid private key loaded from .env.global")
                return key_value
        
        # Special handling for repo URLs - show instructions
        if input_prompt.name in ["control_plane_repo_url", "data_plane_repo_url"]:
            console = Console()
            from rich.prompt import Prompt
            import re
            
            if input_prompt.name == "control_plane_repo_url":
                console.print(f"\n[yellow]Control Plane Repository (infrastructure/platform manifests):[/yellow]")
                console.print("[dim]This repository contains cluster infrastructure and platform configuration[/dim]\n")
            else:
                console.print(f"\n[yellow]Data Plane Repository (tenant/application configs):[/yellow]")
                console.print("[dim]This repository contains tenant services and application configurations[/dim]\n")
            
            while True:
                repo_url = Prompt.ask(input_prompt.prompt).strip()
                if not repo_url:
                    console.print("[red]Repository URL is required[/red]")
                    continue
                
                # Validate URL format
                if not re.match(r"^https://github\.com/[^/]+/[^/]+/?$", repo_url):
                    console.print("[red]Invalid GitHub URL format[/red]")
                    console.print("[dim]Expected: https://github.com/org/repo[/dim]")
                    continue
                
                return repo_url.rstrip('/')
        
        return None  # Use default collection
    
    def get_field_suggestion(self, field_name: str) -> str:
        """Generate suggestions based on platform metadata"""
        org_name = self._platform_metadata.get('organization', '')
        app_name = self._platform_metadata.get('app_name', '')
        
        if field_name == "control_plane_repo_url" and org_name and app_name:
            return f"https://github.com/{org_name}/{app_name}-platform"
        
        if field_name == "data_plane_repo_url" and org_name and app_name:
            return f"https://github.com/{org_name}/{app_name}-tenants"
        
        return None
    
    def init(self) -> List[ScriptReference]:
        """Return init-phase scripts for GitHub API validation"""
        config = GitHubConfig(**self.config)
        
        # Extract org and repo from control plane URL
        import re
        match_cp = re.match(r"^https://github\.com/([^/]+)/([^/]+)/?$", config.control_plane_repo_url.rstrip('/'))
        cp_org = match_cp.group(1)
        cp_repo = match_cp.group(2)
        
        # Extract org and repo from data plane URL
        match_dp = re.match(r"^https://github\.com/([^/]+)/([^/]+)/?$", config.data_plane_repo_url.rstrip('/'))
        dp_org = match_dp.group(1)
        dp_repo = match_dp.group(2)
        
        # Return two separate validation scripts for clearer output
        return [
            ScriptReference(
                package="workflow_engine.adapters.github.scripts",
                resource=GitHubScripts.VALIDATE_ACCESS,
                description=f"Validate GitHub API access to control plane repository ({cp_org}/{cp_repo})",
                timeout=60,
                context_data={
                    "github_app_id": config.github_app_id,
                    "github_app_installation_id": config.github_app_installation_id,
                    "repo_org": cp_org,
                    "repo_name": cp_repo,
                    "repo_type": "control_plane"
                },
                secret_env_vars={
                    "GITHUB_APP_PRIVATE_KEY": config.github_app_private_key.get_secret_value()
                }
            ),
            ScriptReference(
                package="workflow_engine.adapters.github.scripts",
                resource=GitHubScripts.VALIDATE_ACCESS,
                description=f"Validate GitHub API access to data plane repository ({dp_org}/{dp_repo})",
                timeout=60,
                context_data={
                    "github_app_id": config.github_app_id,
                    "github_app_installation_id": config.github_app_installation_id,
                    "repo_org": dp_org,
                    "repo_name": dp_repo,
                    "repo_type": "data_plane"
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
        
        # Extract org and repo from data plane URL
        import re
        match = re.match(r"^https://github\.com/([^/]+)/([^/]+)/?$", config.data_plane_repo_url.rstrip('/'))
        tenant_org = match.group(1)
        tenant_repo = match.group(2)
        
        return [
            ScriptReference(
                package="workflow_engine.adapters.github.scripts",
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
                package="workflow_engine.adapters.github.scripts",
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
        
        # Extract org and repo from data plane URL
        import re
        match = re.match(r"^https://github\.com/([^/]+)/([^/]+)/?$", config.data_plane_repo_url.rstrip('/'))
        tenant_org = match.group(1)
        tenant_repo = match.group(2)
        
        return [
            ScriptReference(
                package="workflow_engine.adapters.github.scripts",
                resource=GitHubScripts.VALIDATE_CREDENTIALS,
                description="Validate GitHub App credentials in cluster",
                timeout=30,
                context_data={
                    "tenant_org": tenant_org,
                    "tenant_repo": f"{tenant_repo}-tenants"
                }
            )
        ]
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate GitHub adapter output (no manifests, no capabilities)"""
        config = GitHubConfig(**self.config)
        
        # Extract org and repo from control plane URL
        import re
        match_cp = re.match(r"^https://github\.com/([^/]+)/([^/]+)/?$", config.control_plane_repo_url.rstrip('/'))
        cp_org = match_cp.group(1)
        cp_repo = match_cp.group(2)
        
        # Extract org and repo from data plane URL
        match_dp = re.match(r"^https://github\.com/([^/]+)/([^/]+)/?$", config.data_plane_repo_url.rstrip('/'))
        dp_org = match_dp.group(1)
        dp_repo = match_dp.group(2)
        
        # GitHub adapter provides data but no capabilities
        # Data will be used by bootstrap scripts and other adapters
        return AdapterOutput(
            manifests={},  # No manifests generated
            stages=[],
            env_vars={},
            capabilities={},  # No capabilities provided
            data={
                "provider": "github",
                "app_id": config.github_app_id,
                "installation_id": config.github_app_installation_id,
                "control_plane_org": cp_org,
                "control_plane_repo": cp_repo,
                "control_plane_repo_url": config.control_plane_repo_url,
                "data_plane_org": dp_org,
                "data_plane_repo": dp_repo,
                "data_plane_repo_url": config.data_plane_repo_url
            }
        )
