"""KSOPS adapter for secrets management with SOPS and Age encryption"""

from enum import Enum
from typing import List, Type, Dict, Any
from pathlib import Path
from pydantic import BaseModel
import yaml
# import typer  # TODO: Re-enable when CLI extensions are needed
from rich.console import Console
from workflow_engine.adapters.base import PlatformAdapter, CLIExtension, InputPrompt, ScriptReference, AdapterOutput
from .config import KSOPSConfig


console = Console()


class KSOPSScripts(str, Enum):
    """Script resource paths (validated at class load)"""
    # Init (1 script - moved from pre_work)
    SETUP_ENV_SECRETS = "init/setup-env-secrets.sh"
    
    # Pre-work (removed - all handled by init/setup-env-secrets.sh)
    
    # Bootstrap (4 scripts)
    INSTALL_KSOPS = "bootstrap/08a-install-ksops.sh"
    INJECT_AGE_KEY = "bootstrap/08c-inject-age-key.sh"
    CREATE_AGE_BACKUP = "bootstrap/08d-create-age-backup.sh"
    DEPLOY_KSOPS = "bootstrap/08e-deploy-ksops-package.sh"
    
    # Post-work (1 script)
    WAIT_KSOPS = "post_work/09c-wait-ksops-sidecar.sh"
    
    # Validation (7 scripts)
    VERIFY_KSOPS = "validation/11-verify-ksops.sh"
    VALIDATE_PACKAGE = "validation/validate-ksops-package.sh"
    VALIDATE_INJECTION = "validation/validate-secret-injection.sh"
    VALIDATE_STORAGE = "validation/validate-age-keys-and-storage.sh"
    VALIDATE_CONFIG = "validation/validate-sops-config.sh"
    VALIDATE_ENCRYPTION = "validation/validate-sops-encryption.sh"
    VALIDATE_DECRYPTION = "validation/validate-age-key-decryption.sh"
    
    # Generators (7 scripts for CLI commands)
    GEN_CREATE_DOT_ENV = "generators/create-dot-env.sh"
    GEN_PLATFORM_SOPS = "generators/generate-platform-sops.sh"
    GEN_SERVICE_ENV_SOPS = "generators/generate-service-env-sops.sh"
    GEN_CORE_SECRETS = "generators/generate-core-secrets.sh"
    GEN_ENV_SECRETS = "generators/generate-env-secrets.sh"
    GEN_GHCR_PULL_SECRET = "generators/generate-ghcr-pull-secret.sh"
    GEN_TENANT_REGISTRY_SECRETS = "generators/generate-tenant-registry-secrets.sh"


class KSOPSAdapter(PlatformAdapter, CLIExtension):
    """KSOPS secrets management adapter"""
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata from KSOPS adapter directory"""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        return yaml.safe_load(metadata_path.read_text())
    
    def get_stage_context(self, stage_name: str, all_adapters_config: Dict[str, Any]) -> Dict[str, Any]:
        """Return non-sensitive context for KSOPS bootstrap stages"""
        from pathlib import Path
        
        repo_root = Path.cwd()
        
        return {
            's3_endpoint': self.config.get('s3_endpoint', ''),
            's3_region': self.config.get('s3_region', ''),
            's3_bucket_name': self.config.get('s3_bucket_name', ''),
            'repo_root': str(repo_root),
            'sops_config_path': str(repo_root / 'platform' / '.sops.yaml'),
            'secrets_dir': str(repo_root / 'platform' / 'generated' / 'argocd' / 'k8' / 'secrets'),
            'age_public_key': self.config.get('age_public_key', ''),
        }
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return KSOPSConfig
    
    def init(self) -> List[ScriptReference]:
        """Return init-phase scripts for Age key setup"""
        config = KSOPSConfig(**self.config)
        
        return [
            ScriptReference(
                package="workflow_engine.adapters.ksops.scripts",
                resource=KSOPSScripts.SETUP_ENV_SECRETS,
                description="Setup environment secrets (Age keys, S3 backup)",
                timeout=300,
                context_data={
                    "s3_endpoint": config.s3_endpoint,
                    "s3_region": config.s3_region,
                    "s3_bucket_name": config.s3_bucket_name
                },
                secret_env_vars={
                    "S3_ACCESS_KEY": config.s3_access_key.get_secret_value(),
                    "S3_SECRET_KEY": config.s3_secret_key.get_secret_value()
                }
            )
        ]
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Interactive prompts for ztc init (GitHub fields removed)"""
        return [
            InputPrompt(
                name="s3_access_key",
                prompt="S3 Access Key",
                type="password",
                help_text="Hetzner S3 access key for Age key backup"
            ),
            InputPrompt(
                name="s3_secret_key",
                prompt="S3 Secret Key",
                type="password",
                help_text="Hetzner S3 secret key"
            ),
            InputPrompt(
                name="s3_endpoint",
                prompt="S3 Endpoint URL (e.g., https://fsn1.your-objectstorage.com)",
                type="string",
                validation=r"^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                help_text="Hetzner S3 endpoint (must be valid URL)"
            ),
            InputPrompt(
                name="s3_region",
                prompt="S3 Region",
                type="string",
                help_text="Auto-detected from endpoint URL"
            ),
            InputPrompt(
                name="s3_bucket_name",
                prompt="S3 Bucket Name (lowercase, hyphens only, 3-63 chars)",
                type="string",
                validation=r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$",
                help_text="S3 bucket naming rules: lowercase letters, numbers, hyphens only. Must start/end with alphanumeric. Length: 3-63 characters."
            )
        ]
    
    def derive_field_value(self, field_name: str, current_config: Dict[str, Any]) -> Any:
        """Extract s3_region from s3_endpoint"""
        if field_name == "s3_region" and "s3_endpoint" in current_config:
            import re
            endpoint = current_config["s3_endpoint"]
            # Extract region from URL like https://fsn1.your-objectstorage.com
            match = re.search(r'https?://([^.]+)\.', endpoint)
            if match:
                return match.group(1)
        return None
    
    def get_field_suggestion(self, field_name: str) -> str:
        """Generate suggestions for KSOPS fields"""
        app_name = self._platform_metadata.get('app_name', '')
        
        if field_name == "s3_bucket_name" and app_name:
            return f"{app_name}-bucket"
        
        return None
    

    
    def pre_work_scripts(self) -> List[ScriptReference]:
        """Pre-work scripts - all handled by init/setup-env-secrets.sh"""
        return []
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """Core KSOPS setup scripts (GitHub scripts removed - now in GitHub adapter)"""
        config = KSOPSConfig(**self.config)
        
        return [
            ScriptReference(
                package="workflow_engine.adapters.ksops.scripts",
                resource=KSOPSScripts.INSTALL_KSOPS,
                description="Install SOPS and Age CLI tools",
                timeout=120,
                context_data={}
            ),
            ScriptReference(
                package="workflow_engine.adapters.ksops.scripts",
                resource=KSOPSScripts.INJECT_AGE_KEY,
                description="Inject Age key into cluster",
                timeout=30,
                context_data={}
            ),
            ScriptReference(
                package="workflow_engine.adapters.ksops.scripts",
                resource=KSOPSScripts.CREATE_AGE_BACKUP,
                description="Create in-cluster encrypted backup",
                timeout=30,
                context_data={}
            ),
            ScriptReference(
                package="workflow_engine.adapters.ksops.scripts",
                resource=KSOPSScripts.DEPLOY_KSOPS,
                description="Deploy KSOPS to ArgoCD",
                timeout=60,
                context_data={}
            )
        ]
    
    def post_work_scripts(self) -> List[ScriptReference]:
        """Wait for KSOPS readiness"""
        return [
            ScriptReference(
                package="workflow_engine.adapters.ksops.scripts",
                resource=KSOPSScripts.WAIT_KSOPS,
                description="Wait for KSOPS init container",
                timeout=300,
                context_data={"timeout_seconds": 300}
            )
        ]
    
    def validation_scripts(self) -> List[ScriptReference]:
        """KSOPS deployment validation"""
        config = KSOPSConfig(**self.config)
        
        return [
            ScriptReference(
                package="workflow_engine.adapters.ksops.scripts",
                resource=KSOPSScripts.VERIFY_KSOPS,
                description="Master validation orchestrator",
                timeout=120,
                context_data={}
            ),
            ScriptReference(
                package="workflow_engine.adapters.ksops.scripts",
                resource=KSOPSScripts.VALIDATE_PACKAGE,
                description="Verify KSOPS deployment",
                timeout=60,
                context_data={}
            ),
            ScriptReference(
                package="workflow_engine.adapters.ksops.scripts",
                resource=KSOPSScripts.VALIDATE_INJECTION,
                description="Verify secret decryption",
                timeout=60,
                context_data={}
            ),
            ScriptReference(
                package="workflow_engine.adapters.ksops.scripts",
                resource=KSOPSScripts.VALIDATE_STORAGE,
                description="Verify key storage",
                timeout=60,
                context_data={
                    "s3_endpoint": config.s3_endpoint,
                    "s3_region": config.s3_region,
                    "s3_bucket_name": config.s3_bucket_name
                },
                secret_env_vars={
                    "S3_ACCESS_KEY": config.s3_access_key.get_secret_value(),
                    "S3_SECRET_KEY": config.s3_secret_key.get_secret_value()
                }
            ),
            ScriptReference(
                package="workflow_engine.adapters.ksops.scripts",
                resource=KSOPSScripts.VALIDATE_CONFIG,
                description="Verify SOPS configuration",
                timeout=30,
                context_data={}
            ),
            ScriptReference(
                package="workflow_engine.adapters.ksops.scripts",
                resource=KSOPSScripts.VALIDATE_ENCRYPTION,
                description="Verify encryption works",
                timeout=30,
                context_data={}
            ),
            ScriptReference(
                package="workflow_engine.adapters.ksops.scripts",
                resource=KSOPSScripts.VALIDATE_DECRYPTION,
                description="Verify active key decrypts",
                timeout=30,
                context_data={}
            )
        ]
    
    def check_health(self) -> None:
        """Pre-flight S3 connectivity check"""
        import boto3
        from botocore.exceptions import ClientError
        from ztc.exceptions import PreFlightError
        
        config = KSOPSConfig(**self.config)
        
        try:
            client = boto3.client(
                's3',
                endpoint_url=config.s3_endpoint,
                aws_access_key_id=config.s3_access_key.get_secret_value(),
                aws_secret_access_key=config.s3_secret_key.get_secret_value(),
                region_name=config.s3_region
            )
            
            # Verify bucket exists and is accessible
            client.head_bucket(Bucket=config.s3_bucket_name)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                raise PreFlightError(
                    f"S3 bucket '{config.s3_bucket_name}' not found",
                    hint="Create bucket or check bucket name in configuration"
                )
            elif error_code == '403':
                raise PreFlightError(
                    f"Access denied to S3 bucket '{config.s3_bucket_name}'",
                    hint="Verify S3 credentials have read/write permissions"
                )
            else:
                raise PreFlightError(f"S3 connectivity check failed: {e}")
        except Exception as e:
            raise PreFlightError(
                f"Cannot reach S3 endpoint {config.s3_endpoint}: {e}",
                hint="Check network connectivity and endpoint URL"
            )
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate .sops.yaml manifest and copy secrets to core overlay"""
        config = KSOPSConfig(**self.config)
        
        # Get Age public key from config (populated by bootstrap)
        age_public_key = self.config.get("age_public_key", "")
        
        # Render .sops.yaml template (with placeholder if key not yet generated)
        template = self.jinja_env.get_template("ksops/.sops.yaml.j2")
        sops_yaml_content = await template.render_async(age_public_key=age_public_key or "# Age key will be generated during bootstrap")
        
        manifests = {".sops.yaml": sops_yaml_content}
        
        # Get ArgoCD repo URL and branch from platform config using cross-adapter access
        repo_url = self.get_cross_adapter_config("argocd", "control_plane_repo_url")
        target_revision = self.get_cross_adapter_config("argocd", "control_plane_repo_branch")
        
        # Render secrets ArgoCD Application
        secrets_app_template = self.jinja_env.get_template("ksops/secrets-application.yaml.j2")
        manifests["argocd/base/00-secrets.yaml"] = await secrets_app_template.render_async(
            repo_url=repo_url,
            target_revision=target_revision
        )
        
        # Move secrets from platform/secrets/ to generated/secrets/
        secrets_source = Path("platform/secrets")
        if secrets_source.exists():
            for secret_file in secrets_source.glob("*.secret.yaml"):
                content = secret_file.read_text()
                manifests[f"secrets/{secret_file.name}"] = content
                secret_file.unlink()  # Delete source file after copying
            
            # Move kustomization.yaml and ksops-generator.yaml if they exist
            for support_file in ["kustomization.yaml", "ksops-generator.yaml"]:
                support_path = secrets_source / support_file
                if support_path.exists():
                    content = support_path.read_text()
                    manifests[f"secrets/{support_file}"] = content
                    support_path.unlink()  # Delete source file after copying
            
            # Remove empty secrets directory
            secrets_source.rmdir()
        
        return AdapterOutput(
            manifests=manifests,
            stages=[],
            env_vars={},
            capabilities={},
            data={"age_public_key": age_public_key} if age_public_key else {}
        )
    
    # TODO: Re-enable CLI extensions when typer dependency is added
    # def get_cli_app(self):
    #     """Return Typer app with secrets management commands"""
    #     app = typer.Typer(help="Secrets management tools")
    #     
    #     app.command(name="init-secrets")(self.init_secrets_command)
    #     app.command(name="init-service-secrets")(self.init_service_secrets_command)
    #     app.command(name="generate-secrets")(self.generate_secrets_command)
    #     app.command(name="create-dot-env")(self.create_dot_env_command)
    #     app.command(name="display-age-key")(self.display_age_private_key_command)
    #     app.command(name="encrypt-secret")(self.encrypt_secret_command)
    #     app.command(name="inject-offline-key")(self.inject_offline_key_command)
    #     app.command(name="recover")(self.recover_command)
    #     app.command(name="rotate-keys")(self.rotate_keys_command)
    #     
    #     return app
    
    # TODO: Re-enable CLI command methods when typer dependency is added
    # def init_secrets_command(self, env: str = typer.Argument(..., help="Environment name")):
    # def init_service_secrets_command(self, service: str = typer.Argument(..., help="Service name"), env: str = typer.Argument(..., help="Environment name")):
    # def generate_secrets_command(self, secret_type: str = typer.Argument(..., help="Secret type (core/env/ghcr/registry)")):
    # def create_dot_env_command(self):
    # def display_age_private_key_command(self):
    # def encrypt_secret_command(self, file: str = typer.Argument(..., help="File to encrypt")):
    # def inject_offline_key_command(self):
    # def recover_command(self):
    # def rotate_keys_command(self):
    pass
