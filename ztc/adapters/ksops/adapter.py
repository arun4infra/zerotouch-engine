"""KSOPS adapter for secrets management with SOPS and Age encryption"""

from enum import Enum
from typing import List, Type, Dict, Any
from pathlib import Path
from pydantic import BaseModel
import yaml
import typer
from rich.console import Console
from ztc.adapters.base import PlatformAdapter, CLIExtension, InputPrompt, ScriptReference, AdapterOutput
from .config import KSOPSConfig


console = Console()


class KSOPSScripts(str, Enum):
    """Script resource paths (validated at class load)"""
    # Init (1 script - moved from pre_work)
    SETUP_ENV_SECRETS = "init/setup-env-secrets.sh"
    
    # Pre-work (5 scripts)
    GENERATE_AGE_KEYS = "pre_work/08b-generate-age-keys.sh"
    RETRIEVE_AGE_KEY = "pre_work/retrieve-age-key.sh"
    INJECT_OFFLINE_KEY = "pre_work/inject-offline-key.sh"
    CREATE_AGE_BACKUP_UTIL = "pre_work/create-age-backup.sh"
    BACKUP_AGE_TO_S3 = "pre_work/08b-backup-age-to-s3.sh"
    
    # Bootstrap (4 scripts - removed INJECT_IDENTITIES, ENV_SUBSTITUTION, BOOTSTRAP_STORAGE)
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
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return KSOPSConfig
    
    def init(self) -> List[ScriptReference]:
        """Return init-phase scripts for Age key setup"""
        config = KSOPSConfig(**self.config)
        
        return [
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
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
    
    def pre_work_scripts(self) -> List[ScriptReference]:
        """Pre-work scripts (automated pre-installation)"""
        config = KSOPSConfig(**self.config)
        
        return [
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.GENERATE_AGE_KEYS,
                description="Generate or retrieve Age keypair",
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
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.SETUP_ENV_SECRETS,
                description="Setup environment-specific secrets",
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
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.RETRIEVE_AGE_KEY,
                description="Retrieve Age key from S3",
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
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.INJECT_OFFLINE_KEY,
                description="Emergency: inject Age key into cluster",
                timeout=30,
                context_data={}
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.CREATE_AGE_BACKUP_UTIL,
                description="Create Age key backup utility",
                timeout=30,
                context_data={}
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.BACKUP_AGE_TO_S3,
                description="Backup Age key to S3",
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
            )
        ]
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """Core KSOPS setup scripts (GitHub scripts removed - now in GitHub adapter)"""
        config = KSOPSConfig(**self.config)
        
        return [
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.INSTALL_KSOPS,
                description="Install SOPS and Age CLI tools",
                timeout=120,
                context_data={}
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.INJECT_AGE_KEY,
                description="Inject Age key into cluster",
                timeout=30,
                context_data={}
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.CREATE_AGE_BACKUP,
                description="Create in-cluster encrypted backup",
                timeout=30,
                context_data={}
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
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
                package="ztc.adapters.ksops.scripts",
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
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.VERIFY_KSOPS,
                description="Master validation orchestrator",
                timeout=120,
                context_data={}
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.VALIDATE_PACKAGE,
                description="Verify KSOPS deployment",
                timeout=60,
                context_data={}
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.VALIDATE_INJECTION,
                description="Verify secret decryption",
                timeout=60,
                context_data={}
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
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
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.VALIDATE_CONFIG,
                description="Verify SOPS configuration",
                timeout=30,
                context_data={}
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.VALIDATE_ENCRYPTION,
                description="Verify encryption works",
                timeout=30,
                context_data={}
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
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
        """Generate .sops.yaml manifest with Age public key"""
        config = KSOPSConfig(**self.config)
        
        # Get Age public key from config (populated by bootstrap)
        age_public_key = self.config.get("age_public_key", "")
        
        # Render .sops.yaml template (with placeholder if key not yet generated)
        template = self.jinja_env.get_template("ksops/.sops.yaml.j2")
        sops_yaml_content = await template.render_async(age_public_key=age_public_key or "# Age key will be generated during bootstrap")
        
        return AdapterOutput(
            manifests={".sops.yaml": sops_yaml_content},
            stages=[],
            env_vars={},
            capabilities={},
            data={"age_public_key": age_public_key} if age_public_key else {}
        )
    
    def get_cli_app(self):
        """Return Typer app with secrets management commands"""
        app = typer.Typer(help="Secrets management tools")
        
        app.command(name="init-secrets")(self.init_secrets_command)
        app.command(name="init-service-secrets")(self.init_service_secrets_command)
        app.command(name="generate-secrets")(self.generate_secrets_command)
        app.command(name="create-dot-env")(self.create_dot_env_command)
        app.command(name="display-age-key")(self.display_age_private_key_command)
        app.command(name="encrypt-secret")(self.encrypt_secret_command)
        app.command(name="inject-offline-key")(self.inject_offline_key_command)
        app.command(name="recover")(self.recover_command)
        app.command(name="rotate-keys")(self.rotate_keys_command)
        
        return app
    
    def init_secrets_command(self, env: str = typer.Argument(..., help="Environment name")):
        """Initialize platform-wide secrets"""
        from ztc.engine.script_executor import ScriptExecutor
        
        console.print(f"[bold blue]Initializing secrets for environment: {env}[/bold blue]")
        
        script_ref = ScriptReference(
            package="ztc.adapters.ksops.scripts",
            resource=KSOPSScripts.GEN_PLATFORM_SOPS,
            description="Generate platform secrets"
        )
        
        executor = ScriptExecutor()
        result = executor.execute(script_ref, context_data={"environment": env})
        
        if result.exit_code == 0:
            console.print("[green]✓[/green] Platform secrets initialized")
        else:
            console.print(f"[red]✗[/red] Failed to initialize secrets")
            console.print(result.stderr)
            raise typer.Exit(1)
    
    def init_service_secrets_command(
        self,
        service: str = typer.Argument(..., help="Service name"),
        env: str = typer.Argument(..., help="Environment name")
    ):
        """Initialize service-specific secrets"""
        from ztc.engine.script_executor import ScriptExecutor
        
        console.print(f"[bold blue]Initializing secrets for service: {service} ({env})[/bold blue]")
        
        script_ref = ScriptReference(
            package="ztc.adapters.ksops.scripts",
            resource=KSOPSScripts.GEN_SERVICE_ENV_SOPS,
            description="Generate service secrets"
        )
        
        executor = ScriptExecutor()
        result = executor.execute(script_ref, context_data={"service": service, "environment": env})
        
        if result.exit_code == 0:
            console.print(f"[green]✓[/green] Service secrets initialized for {service}")
        else:
            console.print(f"[red]✗[/red] Failed to initialize service secrets")
            console.print(result.stderr)
            raise typer.Exit(1)
    
    def generate_secrets_command(self, secret_type: str = typer.Argument(..., help="Secret type (core/env/ghcr/registry)")):
        """Generate specific secret types"""
        from ztc.engine.script_executor import ScriptExecutor
        
        script_map = {
            "core": KSOPSScripts.GEN_CORE_SECRETS,
            "env": KSOPSScripts.GEN_ENV_SECRETS,
            "ghcr": KSOPSScripts.GEN_GHCR_PULL_SECRET,
            "registry": KSOPSScripts.GEN_TENANT_REGISTRY_SECRETS
        }
        
        if secret_type not in script_map:
            console.print(f"[red]✗[/red] Invalid secret type: {secret_type}")
            console.print(f"Valid types: {', '.join(script_map.keys())}")
            raise typer.Exit(1)
        
        console.print(f"[bold blue]Generating {secret_type} secrets[/bold blue]")
        
        script_ref = ScriptReference(
            package="ztc.adapters.ksops.scripts",
            resource=script_map[secret_type],
            description=f"Generate {secret_type} secrets"
        )
        
        executor = ScriptExecutor()
        result = executor.execute(script_ref)
        
        if result.exit_code == 0:
            console.print(f"[green]✓[/green] {secret_type.title()} secrets generated")
        else:
            console.print(f"[red]✗[/red] Failed to generate {secret_type} secrets")
            console.print(result.stderr)
            raise typer.Exit(1)
    
    def create_dot_env_command(self):
        """Generate .env file from encrypted secrets"""
        from ztc.engine.script_executor import ScriptExecutor
        
        console.print("[bold blue]Creating .env file from encrypted secrets[/bold blue]")
        
        config = KSOPSConfig(**self.config)
        
        script_ref = ScriptReference(
            package="ztc.adapters.ksops.scripts",
            resource=KSOPSScripts.GEN_CREATE_DOT_ENV,
            description="Create .env file",
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
        
        executor = ScriptExecutor()
        result = executor.execute(script_ref)
        
        if result.exit_code == 0:
            console.print("[green]✓[/green] .env file created")
        else:
            console.print("[red]✗[/red] Failed to create .env file")
            console.print(result.stderr)
            raise typer.Exit(1)
    
    def display_age_private_key_command(self):
        """Display Age private key (use with caution)"""
        console.print("[yellow]⚠[/yellow]  [bold]Warning: This will display the Age private key[/bold]")
        console.print("Only use this in secure environments")
        
        confirm = typer.confirm("Continue?")
        if not confirm:
            raise typer.Exit(0)
        
        # Read Age key from local file or S3
        age_key_path = Path.home() / ".config" / "sops" / "age" / "keys.txt"
        if age_key_path.exists():
            console.print(f"\n[cyan]Age Private Key:[/cyan]")
            console.print(age_key_path.read_text())
        else:
            console.print("[red]✗[/red] Age key not found locally")
            console.print("Run 'ztc secret recover' to retrieve from S3")
            raise typer.Exit(1)
    
    def encrypt_secret_command(self, file: str = typer.Argument(..., help="File to encrypt")):
        """Encrypt a secret file using SOPS"""
        import subprocess
        
        file_path = Path(file)
        if not file_path.exists():
            console.print(f"[red]✗[/red] File not found: {file}")
            raise typer.Exit(1)
        
        console.print(f"[bold blue]Encrypting {file}[/bold blue]")
        
        try:
            result = subprocess.run(
                ["sops", "--encrypt", "--in-place", str(file_path)],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                console.print(f"[green]✓[/green] File encrypted: {file}")
            else:
                console.print(f"[red]✗[/red] Encryption failed")
                console.print(result.stderr)
                raise typer.Exit(1)
        
        except FileNotFoundError:
            console.print("[red]✗[/red] SOPS not found. Install SOPS first.")
            raise typer.Exit(1)
    
    def inject_offline_key_command(self):
        """Emergency: inject Age key into cluster"""
        from ztc.engine.script_executor import ScriptExecutor
        
        console.print("[yellow]⚠[/yellow]  [bold]Emergency operation: Injecting Age key into cluster[/bold]")
        
        confirm = typer.confirm("This should only be used in emergency situations. Continue?")
        if not confirm:
            raise typer.Exit(0)
        
        script_ref = ScriptReference(
            package="ztc.adapters.ksops.scripts",
            resource=KSOPSScripts.INJECT_OFFLINE_KEY,
            description="Inject Age key offline"
        )
        
        executor = ScriptExecutor()
        result = executor.execute(script_ref)
        
        if result.exit_code == 0:
            console.print("[green]✓[/green] Age key injected into cluster")
        else:
            console.print("[red]✗[/red] Failed to inject Age key")
            console.print(result.stderr)
            raise typer.Exit(1)
    
    def recover_command(self):
        """Recover Age key from S3 backup"""
        from ztc.engine.script_executor import ScriptExecutor
        
        console.print("[bold blue]Recovering Age key from S3 backup[/bold blue]")
        
        config = KSOPSConfig(**self.config)
        
        script_ref = ScriptReference(
            package="ztc.adapters.ksops.scripts",
            resource=KSOPSScripts.RETRIEVE_AGE_KEY,
            description="Retrieve Age key from S3",
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
        
        executor = ScriptExecutor()
        result = executor.execute(script_ref)
        
        if result.exit_code == 0:
            console.print("[green]✓[/green] Age key recovered from S3")
        else:
            console.print("[red]✗[/red] Failed to recover Age key")
            console.print(result.stderr)
            raise typer.Exit(1)
    
    def rotate_keys_command(self):
        """Rotate Age encryption keys and re-encrypt secrets"""
        console.print("[yellow]⚠[/yellow]  [bold]Key rotation is a destructive operation[/bold]")
        console.print("This will:")
        console.print("  1. Generate new Age keypair")
        console.print("  2. Re-encrypt all secrets with new key")
        console.print("  3. Update cluster with new key")
        console.print("  4. Backup old key to S3")
        
        confirm = typer.confirm("Continue with key rotation?")
        if not confirm:
            raise typer.Exit(0)
        
        console.print("[red]✗[/red] Key rotation not yet implemented")
        console.print("Manual steps:")
        console.print("  1. Generate new key: age-keygen -o new-keys.txt")
        console.print("  2. Update .sops.yaml with new public key")
        console.print("  3. Re-encrypt: find . -name '*.enc.yaml' -exec sops updatekeys {} \\;")
        console.print("  4. Update cluster secret: kubectl create secret generic sops-age --from-file=keys.txt=new-keys.txt")
        raise typer.Exit(1)
