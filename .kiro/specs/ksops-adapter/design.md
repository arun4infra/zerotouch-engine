# Design Document: KSOPS Adapter

## Overview

The KSOPS adapter integrates SOPS (Secrets OPerationS) with Age encryption into the ZeroTouch Composition Engine. It follows the standard ZTC adapter pattern, providing secrets management capabilities through:

- Configuration validation via Pydantic models
- Script extraction with context file generation
- Capability-based dependency resolution (requires kubernetes-api, provides secrets-management)
- Integration with adapter registry for CLI discovery

The adapter extracts 14 scripts from zerotouch-platform, inlines helper functions, and adapts them to use JSON context files instead of CLI arguments.

## Architecture

### Component Structure

```
ztc/adapters/ksops/
├── adapter.py              # KSOPSAdapter class
├── adapter.yaml            # Metadata and capabilities
├── config.py               # KSOPSConfig Pydantic model
├── templates/              # (empty - no manifests)
└── scripts/
    ├── bootstrap/          # 8 scripts
    │   ├── 00-inject-identities.sh
    │   ├── 03-bootstrap-storage.sh
    │   ├── 08a-install-ksops.sh
    │   ├── 08b-generate-age-keys.sh
    │   ├── 08c-inject-age-key.sh
    │   ├── 08d-create-age-backup.sh
    │   ├── apply-env-substitution.sh
    │   └── 08e-deploy-ksops-package.sh
    ├── post_work/          # 1 script
    │   └── 09c-wait-ksops-sidecar.sh
    └── validation/         # 7 scripts
        ├── 11-verify-ksops.sh
        ├── validate-ksops-package.sh
        ├── validate-secret-injection.sh
        ├── validate-age-keys-and-storage.sh
        ├── validate-sops-config.sh
        ├── validate-sops-encryption.sh
        └── validate-age-key-decryption.sh
```

### Capability Dependencies

```mermaid
graph LR
    A[Talos Adapter] -->|provides| B[kubernetes-api]
    B -->|requires| C[KSOPS Adapter]
    C -->|provides| D[secrets-management]
```

## Components and Interfaces

### 1. Configuration Model (config.py)

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional

class KSOPSConfig(BaseModel):
    """KSOPS adapter configuration"""
    
    # S3 Configuration
    s3_access_key: str = Field(..., min_length=1)
    s3_secret_key: str = Field(..., min_length=1)
    s3_endpoint: str = Field(..., pattern=r'^https?://')
    s3_region: str = Field(..., min_length=1)
    s3_bucket_name: str = Field(..., min_length=1)
    
    # GitHub App Configuration
    github_app_id: int = Field(..., gt=0)
    github_app_installation_id: int = Field(..., gt=0)
    github_app_private_key: str = Field(..., min_length=1)
    
    # Tenant Configuration
    tenant_org_name: str = Field(..., pattern=r'^[a-zA-Z0-9-]+$')
    tenant_repo_name: str = Field(..., pattern=r'^[a-zA-Z0-9-]+$')
    
    @field_validator('github_app_private_key')
    @classmethod
    def validate_pem_format(cls, v: str) -> str:
        """Validate PEM format"""
        if not v.startswith('-----BEGIN'):
            raise ValueError('Private key must be in PEM format')
        return v
```

### 2. Adapter Class (adapter.py)

```python
from enum import Enum
from typing import List, Type
from ztc.adapters.base import PlatformAdapter, InputPrompt, ScriptReference, AdapterOutput
from ztc.interfaces.capabilities import SecretsManagementCapability
from .config import KSOPSConfig

class KSOPSScripts(str, Enum):
    """Script resource paths (validated at class load)"""
    # Bootstrap
    INJECT_IDENTITIES = "bootstrap/00-inject-identities.sh"
    BOOTSTRAP_STORAGE = "bootstrap/03-bootstrap-storage.sh"
    INSTALL_KSOPS = "bootstrap/08a-install-ksops.sh"
    GENERATE_AGE_KEYS = "bootstrap/08b-generate-age-keys.sh"
    INJECT_AGE_KEY = "bootstrap/08c-inject-age-key.sh"
    CREATE_AGE_BACKUP = "bootstrap/08d-create-age-backup.sh"
    ENV_SUBSTITUTION = "bootstrap/apply-env-substitution.sh"
    DEPLOY_KSOPS = "bootstrap/08e-deploy-ksops-package.sh"
    
    # Post-work
    WAIT_KSOPS = "post_work/09c-wait-ksops-sidecar.sh"
    
    # Validation
    VERIFY_KSOPS = "validation/11-verify-ksops.sh"
    VALIDATE_PACKAGE = "validation/validate-ksops-package.sh"
    VALIDATE_INJECTION = "validation/validate-secret-injection.sh"
    VALIDATE_STORAGE = "validation/validate-age-keys-and-storage.sh"
    VALIDATE_CONFIG = "validation/validate-sops-config.sh"
    VALIDATE_ENCRYPTION = "validation/validate-sops-encryption.sh"
    VALIDATE_DECRYPTION = "validation/validate-age-key-decryption.sh"

class KSOPSAdapter(PlatformAdapter):
    """KSOPS secrets management adapter"""
    
    @property
    def config_model(self) -> Type[BaseModel]:
        return KSOPSConfig
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Interactive prompts for ztc init"""
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
                prompt="S3 Endpoint URL",
                type="string",
                default="https://fsn1.your-objectstorage.com",
                help_text="Hetzner S3 endpoint"
            ),
            InputPrompt(
                name="s3_region",
                prompt="S3 Region",
                type="string",
                default="fsn1",
                help_text="Hetzner S3 region"
            ),
            InputPrompt(
                name="s3_bucket_name",
                prompt="S3 Bucket Name",
                type="string",
                help_text="Bucket for Age key backups"
            ),
            InputPrompt(
                name="github_app_id",
                prompt="GitHub App ID",
                type="string",
                help_text="GitHub App ID for ArgoCD authentication"
            ),
            InputPrompt(
                name="github_app_installation_id",
                prompt="GitHub App Installation ID",
                type="string",
                help_text="Installation ID for your organization"
            ),
            InputPrompt(
                name="github_app_private_key",
                prompt="GitHub App Private Key",
                type="password",
                help_text="PEM-formatted private key"
            ),
            InputPrompt(
                name="tenant_org_name",
                prompt="Tenant Organization Name",
                type="string",
                help_text="GitHub organization name"
            ),
            InputPrompt(
                name="tenant_repo_name",
                prompt="Tenant Repository Name",
                type="string",
                help_text="Repository name for tenant config"
            )
        ]
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """Core KSOPS setup scripts"""
        config = KSOPSConfig(**self.config)
        
        return [
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.INJECT_IDENTITIES,
                description="Inject GitHub App credentials",
                timeout=30,
                context_data={
                    "github_app_id": config.github_app_id,
                    "github_app_installation_id": config.github_app_installation_id,
                    "github_app_private_key": config.github_app_private_key
                }
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.BOOTSTRAP_STORAGE,
                description="Bootstrap Hetzner Object Storage",
                timeout=120,
                context_data={
                    "s3_access_key": config.s3_access_key,
                    "s3_secret_key": config.s3_secret_key,
                    "s3_endpoint": config.s3_endpoint,
                    "s3_region": config.s3_region
                }
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.INSTALL_KSOPS,
                description="Install SOPS and Age CLI tools",
                timeout=120
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.GENERATE_AGE_KEYS,
                description="Generate or retrieve Age keypair",
                timeout=60,
                context_data={
                    "s3_access_key": config.s3_access_key,
                    "s3_secret_key": config.s3_secret_key,
                    "s3_endpoint": config.s3_endpoint,
                    "s3_region": config.s3_region,
                    "s3_bucket_name": config.s3_bucket_name
                }
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.INJECT_AGE_KEY,
                description="Inject Age key into cluster",
                timeout=30
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.CREATE_AGE_BACKUP,
                description="Create in-cluster encrypted backup",
                timeout=30
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.ENV_SUBSTITUTION,
                description="Substitute tenant repo URLs",
                timeout=30,
                context_data={
                    "tenant_org_name": config.tenant_org_name,
                    "tenant_repo_name": config.tenant_repo_name
                }
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.DEPLOY_KSOPS,
                description="Deploy KSOPS to ArgoCD",
                timeout=60
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
                timeout=120
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.VALIDATE_PACKAGE,
                description="Verify KSOPS deployment",
                timeout=60
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.VALIDATE_INJECTION,
                description="Verify secret decryption",
                timeout=60
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.VALIDATE_STORAGE,
                description="Verify key storage",
                timeout=60,
                context_data={
                    "s3_access_key": config.s3_access_key,
                    "s3_secret_key": config.s3_secret_key,
                    "s3_endpoint": config.s3_endpoint,
                    "s3_region": config.s3_region,
                    "s3_bucket_name": config.s3_bucket_name
                }
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.VALIDATE_CONFIG,
                description="Verify SOPS configuration",
                timeout=30
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.VALIDATE_ENCRYPTION,
                description="Verify encryption works",
                timeout=30
            ),
            ScriptReference(
                package="ztc.adapters.ksops.scripts",
                resource=KSOPSScripts.VALIDATE_DECRYPTION,
                description="Verify active key decrypts",
                timeout=30
            )
        ]
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate capability data (no manifests)"""
        config = KSOPSConfig(**self.config)
        
        # Verify kubernetes-api capability available
        k8s_capability = ctx.get_capability_data('kubernetes-api')
        if not k8s_capability:
            raise ValueError("KSOPS requires kubernetes-api capability")
        
        # Create secrets-management capability
        secrets_capability = SecretsManagementCapability(
            provider="ksops",
            s3_bucket=config.s3_bucket_name,
            sops_config_path=".sops.yaml"
        )
        
        return AdapterOutput(
            manifests={},  # No manifests (scripts handle deployment)
            stages=[],
            env_vars={},
            capabilities={
                "secrets-management": secrets_capability
            },
            data={
                "s3_bucket": config.s3_bucket_name,
                "tenant_org": config.tenant_org_name,
                "tenant_repo": config.tenant_repo_name
            }
        )
```

### 3. Adapter Metadata (adapter.yaml)

```yaml
name: ksops
display_name: KSOPS (SOPS + Age)
version: 1.0.0
phase: secrets
selection_group: secrets_management
is_default: true

capabilities:
  provides:
    - secrets-management
  requires:
    - kubernetes-api

supported_versions:
  - v1.0.0

default_version: v1.0.0

description: |
  KSOPS provides GitOps-based secrets management using SOPS with Age encryption.
  Integrates with ArgoCD for automatic secret decryption during sync.
```

### 4. Capability Contract (capabilities.py addition)

```python
from pydantic import BaseModel

class SecretsManagementCapability(BaseModel):
    """Secrets management capability contract"""
    provider: str  # "ksops", "sealed-secrets", "external-secrets"
    s3_bucket: str
    sops_config_path: str
```

## Data Models

### Context File Schema

Each script receives a JSON context file via `$ZTC_CONTEXT_FILE`:

```json
{
  "s3_access_key": "string",
  "s3_secret_key": "string",
  "s3_endpoint": "https://...",
  "s3_region": "string",
  "s3_bucket_name": "string",
  "github_app_id": 123,
  "github_app_installation_id": 456,
  "github_app_private_key": "-----BEGIN...",
  "tenant_org_name": "string",
  "tenant_repo_name": "string",
  "timeout_seconds": 300
}
```

### Script Context Reading Pattern

All scripts follow this pattern:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Validate context file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

# Parse with jq
S3_ACCESS_KEY=$(jq -r '.s3_access_key' "$ZTC_CONTEXT_FILE")
S3_SECRET_KEY=$(jq -r '.s3_secret_key' "$ZTC_CONTEXT_FILE")

# Validate required fields
if [[ -z "$S3_ACCESS_KEY" || "$S3_ACCESS_KEY" == "null" ]]; then
    echo "ERROR: s3_access_key required" >&2
    exit 1
fi

# Core logic (unchanged from zerotouch-platform)
# ...
```

## Error Handling

### Configuration Validation Errors

```python
try:
    config = KSOPSConfig(**user_input)
except ValidationError as e:
    # ZTC displays field-level errors
    raise ConfigurationError(
        "Invalid KSOPS configuration",
        details=e.errors()
    )
```

### Capability Dependency Errors

```python
if not ctx.get_capability_data('kubernetes-api'):
    raise CapabilityError(
        "KSOPS requires kubernetes-api capability",
        hint="Add Talos or another Kubernetes provider adapter"
    )
```

### Script Execution Errors

Scripts exit with non-zero codes on failure. ZTC captures:
- Exit code
- stdout/stderr
- Script name
- Context data (sanitized)

## Testing Strategy

### Unit Tests

Test adapter configuration and interface compliance:

```python
def test_config_validation():
    """Test KSOPSConfig validation"""
    config = KSOPSConfig(
        s3_access_key="test",
        s3_secret_key="test",
        s3_endpoint="https://s3.example.com",
        s3_region="us-east-1",
        s3_bucket_name="test-bucket",
        github_app_id=123,
        github_app_installation_id=456,
        github_app_private_key="-----BEGIN RSA PRIVATE KEY-----\n...",
        tenant_org_name="test-org",
        tenant_repo_name="test-repo"
    )
    assert config.s3_bucket_name == "test-bucket"

def test_invalid_pem_format():
    """Test PEM validation rejects invalid keys"""
    with pytest.raises(ValidationError):
        KSOPSConfig(
            github_app_private_key="not-a-pem-key",
            # ... other fields
        )

def test_script_references():
    """Test bootstrap scripts return correct references"""
    adapter = KSOPSAdapter(valid_config)
    scripts = adapter.bootstrap_scripts()
    assert len(scripts) == 6
    assert scripts[0].resource == KSOPSScripts.INSTALL_KSOPS

def test_capability_provision():
    """Test adapter provides secrets-management capability"""
    adapter = KSOPSAdapter(valid_config)
    ctx = MockContextSnapshot()
    output = await adapter.render(ctx)
    assert "secrets-management" in output.capabilities
```

### Integration Tests

Test adapter rendering with mocked context:

```python
@pytest.mark.asyncio
async def test_render_with_k8s_capability():
    """Test render accesses kubernetes-api capability"""
    config = valid_ksops_config()
    adapter = KSOPSAdapter(config)
    
    ctx = MockContextSnapshot()
    ctx.add_capability("kubernetes-api", KubernetesAPICapability(...))
    
    output = await adapter.render(ctx)
    
    assert output.capabilities["secrets-management"].provider == "ksops"
    assert output.data["s3_bucket"] == config["s3_bucket_name"]

@pytest.mark.asyncio
async def test_render_fails_without_k8s():
    """Test render fails without kubernetes-api"""
    adapter = KSOPSAdapter(valid_ksops_config())
    ctx = MockContextSnapshot()  # No kubernetes-api
    
    with pytest.raises(ValueError, match="requires kubernetes-api"):
        await adapter.render(ctx)
```

### Property-Based Tests

Property tests validate universal correctness properties across randomized inputs. Each property test runs minimum 100 iterations with generated data.


## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property 1: Configuration Validation Completeness

*For any* dictionary containing all required KSOPS configuration fields with valid values, creating a KSOPSConfig instance should succeed and preserve all field values.

**Validates: Requirements 3.1-3.10**

### Property 2: Invalid Configuration Rejection

*For any* configuration dictionary with invalid field values (negative integers, malformed URLs, non-PEM keys, invalid patterns), KSOPSConfig validation should raise ValidationError with field-specific error details.

**Validates: Requirements 3.1-3.10, 16.1**

### Property 3: Input Prompt Completeness

*For any* KSOPS adapter instance, get_required_inputs() should return prompts for all 10 required configuration fields (s3_access_key, s3_secret_key, s3_endpoint, s3_region, s3_bucket_name, github_app_id, github_app_installation_id, github_app_private_key, tenant_org_name, tenant_repo_name).

**Validates: Requirements 4.1-4.10**

### Property 4: Bootstrap Script Reference Completeness

*For any* valid KSOPS configuration, bootstrap_scripts() should return exactly 8 ScriptReference objects with resources matching the KSOPSScripts enum values for bootstrap phase.

**Validates: Requirements 5.1-5.6**

### Property 5: Post-Work Script Reference Completeness

*For any* valid KSOPS configuration, post_work_scripts() should return exactly 1 ScriptReference object for the KSOPS sidecar wait script.

**Validates: Requirements 6.1-6.2**

### Property 6: Validation Script Reference Completeness

*For any* valid KSOPS configuration, validation_scripts() should return exactly 7 ScriptReference objects with resources matching the KSOPSScripts enum values for validation phase.

**Validates: Requirements 7.1-7.7**

### Property 7: Context Data JSON Serializability

*For any* ScriptReference returned by bootstrap_scripts(), post_work_scripts(), or validation_scripts(), the context_data dictionary should be JSON-serializable without errors.

**Validates: Requirements 9.1, 9.3**

### Property 8: Context Data Required Fields

*For any* ScriptReference with non-empty context_data, all values should be non-null and all string values should be non-empty.

**Validates: Requirements 9.4**

### Property 9: Capability Provision with Valid Context

*For any* valid KSOPS configuration and ContextSnapshot containing kubernetes-api capability, render() should return AdapterOutput with secrets-management capability containing provider, s3_bucket, and sops_config_path fields.

**Validates: Requirements 10.1-10.3, 13.1-13.5**

### Property 10: Capability Dependency Enforcement

*For any* valid KSOPS configuration and ContextSnapshot without kubernetes-api capability, render() should raise ValueError with message containing "requires kubernetes-api".

**Validates: Requirements 11.1-11.3**

### Property 11: Adapter Metadata Completeness

*For any* KSOPS adapter instance, load_metadata() should return a dictionary containing all required fields: name, version, phase, selection_group, provides (list), requires (list), supported_versions (list), default_version.

**Validates: Requirements 2.1-2.7, 17.1-17.3**

### Property 12: Script Enum Validation

*For any* KSOPSScripts enum value, the corresponding script file should exist in the package at the specified path.

**Validates: Requirements 14.1-14.3**

## Property Reflection

After reviewing all properties:

- Properties 1 and 2 are complementary (valid vs invalid configs) - both needed
- Property 3 is unique (input prompts)
- Properties 4, 5, 6 are similar but test different script phases - all needed for completeness
- Properties 7 and 8 both test context data but different aspects (serializability vs content) - both needed
- Properties 9 and 10 are complementary (success vs failure cases) - both needed
- Property 11 is unique (metadata)
- Property 12 is unique (enum validation)

No redundancy detected. All properties provide unique validation value.



## CLI Commands

The KSOPS adapter provides user-facing CLI commands for manual secret management operations. Commands are registered under the **`secret` category** (not `ksops`) to maintain compatibility with other secrets management adapters.

### Category-Based CLI Design

KSOPS implements the `CLIExtension` mixin to provide commands under the `secret` category namespace. This allows users to switch between secrets adapters (KSOPS, Sealed Secrets, etc.) without changing their CLI workflows.

**Command Pattern:**
```bash
ztc secret <command> [args]    # Category-based (correct)
# NOT: ztc ksops <command>     # Tool-specific (incorrect)
```

### CLI Extension Implementation

```python
from ztc.adapters.base import PlatformAdapter, CLIExtension
import typer

class KSOPSAdapter(PlatformAdapter, CLIExtension):
    """KSOPS adapter with lifecycle and CLI commands"""
    
    def get_cli_category(self) -> str:
        """Return CLI category name
        
        Maps selection_group 'secrets_management' to category 'secret'
        """
        return "secret"
    
    def get_cli_app(self) -> typer.Typer:
        """Register secrets management CLI commands
        
        Commands registered here appear under 'ztc secret' namespace.
        All secrets adapters must implement compatible commands.
        """
        app = typer.Typer(help="Secrets management tools")
        
        # Secret initialization commands
        app.command(name="init-secrets")(self.init_secrets_command)
        app.command(name="init-service-secrets")(self.init_service_secrets_command)
        app.command(name="generate-secrets")(self.generate_secrets_command)
        
        # Secret management commands
        app.command(name="create-dot-env")(self.create_dot_env_command)
        app.command(name="display-age-private-key")(self.display_age_private_key_command)
        app.command(name="encrypt-secret")(self.encrypt_secret_command)
        
        # Emergency recovery commands
        app.command(name="inject-offline-key")(self.inject_offline_key_command)
        app.command(name="recover")(self.recover_command)
        
        # Maintenance commands
        app.command(name="rotate-keys")(self.rotate_keys_command)
        
        return app
```

### Command Mapping

| CLI Command | Source Script | Description |
|-------------|---------------|-------------|
| `ztc secret init-secrets <env>` | `setup-env-secrets.sh` | Initialize environment-specific secrets |
| `ztc secret init-service-secrets <service>` | `generate-service-env-sops.sh` | Initialize service-specific secrets |
| `ztc secret generate-secrets` | `generate-platform-sops.sh` | Generate encrypted platform secrets |
| `ztc secret create-dot-env` | `create-dot-env.sh` | Generate .env from encrypted secrets |
| `ztc secret display-age-private-key` | `retrieve-age-key.sh` | Display Age key for GitHub secrets |
| `ztc secret encrypt-secret <file>` | SOPS wrapper | Encrypt individual secret file |
| `ztc secret inject-offline-key` | `inject-offline-key.sh` | Emergency: inject Age key into cluster |
| `ztc secret recover` | Disaster recovery orchestrator | Full disaster recovery workflow |
| `ztc secret rotate-keys` | Key rotation workflow | Rotate Age keys and re-encrypt |

### Command Handler Pattern

Each command handler follows this pattern:

```python
def init_secrets_command(self, env: str):
    """Initialize environment-specific secrets
    
    Args:
        env: Environment name (production, staging, etc.)
    """
    from ztc.engine.script_executor import ScriptExecutor
    from rich.console import Console
    
    console = Console()
    
    # 1. Get script reference
    script_ref = ScriptReference(
        package="ztc.adapters.ksops.scripts.utilities",
        resource="setup-env-secrets.sh",
        description="Initialize environment secrets"
    )
    
    # 2. Generate context data from arguments and config
    context_data = {
        "env": env,
        "s3_access_key": self.config["s3_access_key"],
        "s3_secret_key": self.config["s3_secret_key"],
        "s3_endpoint": self.config["s3_endpoint"],
        "s3_region": self.config["s3_region"],
        "s3_bucket_name": self.config["s3_bucket_name"]
    }
    
    # 3. Execute script with context
    executor = ScriptExecutor()
    result = executor.execute(script_ref, context_data)
    
    # 4. Display results
    if result.exit_code == 0:
        console.print(f"[green]✓[/green] Secrets initialized for {env}")
    else:
        console.print(f"[red]✗[/red] Failed to initialize secrets")
        console.print(f"Error: {result.stderr}")
        raise typer.Exit(1)
```

### Command Handler Implementations

```python
def init_service_secrets_command(self, service: str):
    """Initialize service-specific secrets"""
    # Extract generate-service-env-sops.sh
    # Generate context with service name
    # Execute and display results
    pass

def generate_secrets_command(self):
    """Generate all platform secrets"""
    # Extract generate-platform-sops.sh
    # Generate context from config
    # Execute and display results
    pass

def create_dot_env_command(self):
    """Generate .env from encrypted secrets"""
    # Extract create-dot-env.sh
    # Generate context with Age key
    # Execute and display results
    pass

def display_age_private_key_command(self):
    """Display Age private key for GitHub secrets"""
    # Extract retrieve-age-key.sh
    # Generate context with S3 credentials
    # Execute and display key
    pass

def encrypt_secret_command(self, file: str):
    """Encrypt individual secret file"""
    # Wrap SOPS CLI with Age key
    # Execute encryption
    # Display results
    pass

def inject_offline_key_command(self):
    """Emergency: inject Age key into cluster"""
    # Extract inject-offline-key.sh
    # Prompt for Age key (break-glass)
    # Generate context and execute
    pass

def recover_command(self):
    """Full disaster recovery workflow"""
    # Orchestrate multiple recovery scripts
    # Guide user through recovery steps
    # Execute recovery sequence
    pass

def rotate_keys_command(self):
    """Rotate Age keys and re-encrypt secrets"""
    # Generate new Age keypair
    # Re-encrypt all secrets with new key
    # Update cluster and S3 storage
    pass
```

### Secrets Category Command Contract

KSOPS implements the standard secrets management category commands. All secrets adapters (KSOPS, Sealed Secrets, External Secrets) must implement these commands with compatible signatures:

**Required Commands:**
- `init-secrets <env>` - Initialize environment secrets
- `create-dot-env` - Generate .env file
- `encrypt-secret <file>` - Encrypt secret file
- `rotate-keys` - Rotate encryption keys

**Optional Commands:**
- `init-service-secrets <service>` - Service-specific secrets
- `generate-secrets` - Generate all secrets
- `display-age-private-key` - Display encryption key
- `inject-offline-key` - Emergency key injection
- `recover` - Disaster recovery

### CLI Registration

CLI commands are registered automatically when KSOPS is selected in `platform.yaml`:

```yaml
# platform.yaml
adapters:
  ksops:
    version: v1.0.0
    s3_bucket_name: my-secrets-bucket
    # ... other config
```

On CLI startup, ZTC:
1. Loads platform.yaml
2. Discovers KSOPS implements CLIExtension
3. Calls `get_cli_category()` → returns "secret"
4. Calls `get_cli_app()` → returns Typer instance with commands
5. Registers commands under `ztc secret` namespace

### Usage Examples

```bash
# Initialize secrets for production environment
ztc secret init-secrets production

# Generate .env file from encrypted secrets
ztc secret create-dot-env

# Encrypt a new secret file
ztc secret encrypt-secret config/database.yaml

# Display Age private key for GitHub Actions
ztc secret display-age-private-key

# Rotate encryption keys
ztc secret rotate-keys

# Emergency: inject Age key into cluster
ztc secret inject-offline-key

# Full disaster recovery
ztc secret recover
```
| `ztc secret inject-offline-key` | `inject-offline-key.sh` | Emergency: inject Age key into cluster |
| `ztc secret recover` | Disaster recovery orchestrator | Full disaster recovery workflow |
| `ztc secret rotate-keys` | Key rotation workflow | Rotate Age keys and re-encrypt |

### Script Source Reference

All scripts are extracted from `zerotouch-platform/scripts/bootstrap/infra/secrets/`. For clarification on script logic and implementation details, refer to the original scripts at:

**`zerotouch-platform/scripts/bootstrap/infra/secrets/`**

## Complete Script Inventory

### Bootstrap Scripts (Pipeline Execution)

| ZTC Script | Original Source | Context Data | Description |
|------------|-----------------|--------------|-------------|
| `00-inject-identities.sh` | `infra/secrets/00-inject-identities.sh` | `github_app_id`, `github_app_installation_id`, `github_app_private_key` | Inject GitHub App credentials into ArgoCD namespace |
| `03-bootstrap-storage.sh` | `infra/secrets/03-bootstrap-storage.sh` | `s3_access_key`, `s3_secret_key`, `s3_endpoint`, `s3_region` | Provision Hetzner S3 buckets with Object Lock |
| `08a-install-ksops.sh` | `infra/secrets/ksops/08a-install-ksops.sh` | None | Install SOPS and Age CLI tools |
| `08b-generate-age-keys.sh` | `infra/secrets/ksops/08b-generate-age-keys.sh` | `s3_access_key`, `s3_secret_key`, `s3_endpoint`, `s3_region`, `s3_bucket_name` | Generate Age keypair or retrieve from S3 |
| `08c-inject-age-key.sh` | `infra/secrets/ksops/08c-inject-age-key.sh` | None | Inject Age private key into cluster as secret |
| `08d-create-age-backup.sh` | `infra/secrets/ksops/08d-create-age-backup.sh` | None | Create encrypted in-cluster Age key backup |
| `apply-env-substitution.sh` | `infra/secrets/ksops/apply-env-substitution.sh` | `tenant_org_name`, `tenant_repo_name` | Substitute tenant repo URLs in ArgoCD manifests |
| `08e-deploy-ksops-package.sh` | `infra/secrets/ksops/08e-deploy-ksops-package.sh` | None | Deploy KSOPS package to ArgoCD (init container + CronJob) |

### Post-Work Scripts (Readiness Verification)

| ZTC Script | Original Source | Context Data | Description |
|------------|-----------------|--------------|-------------|
| `09c-wait-ksops-sidecar.sh` | `wait/09c-wait-ksops-sidecar.sh` | `timeout_seconds` | Wait for KSOPS init container completion |

### Validation Scripts (Deployment Verification)

| ZTC Script | Original Source | Context Data | Description |
|------------|-----------------|--------------|-------------|
| `11-verify-ksops.sh` | `validation/11-verify-ksops.sh` | None | Master validation orchestrator |
| `validate-ksops-package.sh` | `validation/secrets/validate-ksops-package.sh` | None | Verify KSOPS deployment to ArgoCD |
| `validate-secret-injection.sh` | `validation/secrets/validate-secret-injection.sh` | None | Verify secret decryption works |
| `validate-age-keys-and-storage.sh` | `validation/secrets/validate-age-keys-and-storage.sh` | `s3_access_key`, `s3_secret_key`, `s3_endpoint`, `s3_region`, `s3_bucket_name` | Verify Age key storage in S3 |
| `validate-sops-config.sh` | `validation/secrets/validate-sops-config.sh` | None | Verify .sops.yaml configuration |
| `validate-sops-encryption.sh` | `validation/secrets/validate-sops-encryption.sh` | None | Verify encryption functionality |
| `validate-age-key-decryption.sh` | `validation/secrets/validate-age-key-decryption.sh` | None | Verify active key can decrypt secrets |

### Utility Scripts (Manual Operations)

| ZTC Script | Original Source | Context Data | Description |
|------------|-----------------|--------------|-------------|
| `08b-backup-age-to-s3.sh` | `infra/secrets/ksops/08b-backup-age-to-s3.sh` | `s3_access_key`, `s3_secret_key`, `s3_endpoint`, `s3_region`, `s3_bucket_name`, `age_private_key` | Backup Age key to S3 with recovery encryption |
| `create-age-backup.sh` | `infra/secrets/ksops/create-age-backup.sh` | None | Create in-cluster encrypted backup utility |
| `inject-offline-key.sh` | `infra/secrets/ksops/inject-offline-key.sh` | `namespace`, `secret_name`, `age_private_key` | Emergency break-glass: inject Age key |
| `retrieve-age-key.sh` | `infra/secrets/ksops/retrieve-age-key.sh` | `env`, `s3_access_key`, `s3_secret_key`, `s3_endpoint`, `s3_region`, `s3_bucket_name` | Retrieve Age key from S3 for GitHub secrets |
| `setup-env-secrets.sh` | `infra/secrets/ksops/setup-env-secrets.sh` | `env`, `s3_access_key`, `s3_secret_key`, `s3_endpoint`, `s3_region`, `s3_bucket_name` | Initialize environment-specific secrets |

### Generator Scripts (Secret Creation)

| ZTC Script | Original Source | Context Data | Description |
|------------|-----------------|--------------|-------------|
| `create-dot-env.sh` | `infra/secrets/ksops/generate-sops/create-dot-env.sh` | `env`, `age_private_key`, `s3_access_key`, `s3_secret_key`, `s3_endpoint`, `s3_region`, `s3_bucket_name` | Generate .env from encrypted secrets in Git |
| `generate-core-secrets.sh` | `infra/secrets/ksops/generate-sops/generate-core-secrets.sh` | `env`, `age_public_key` | Generate core platform secrets |
| `generate-env-secrets.sh` | `infra/secrets/ksops/generate-sops/generate-env-secrets.sh` | `env`, `age_public_key` | Generate environment-specific secrets |
| `generate-ghcr-pull-secret.sh` | `infra/secrets/ksops/generate-sops/generate-ghcr-pull-secret.sh` | `env`, `age_public_key`, `ghcr_token` | Generate GitHub Container Registry pull secret |
| `generate-platform-sops.sh` | `infra/secrets/ksops/generate-sops/generate-platform-sops.sh` | `env`, `age_public_key` | Generate all platform SOPS secrets |
| `generate-service-env-sops.sh` | `infra/secrets/ksops/generate-sops/generate-service-env-sops.sh` | `service_name`, `env`, `age_public_key` | Generate service-specific environment secrets |
| `generate-tenant-registry-secrets.sh` | `infra/secrets/ksops/generate-sops/generate-tenant-registry-secrets.sh` | `env`, `age_public_key` | Generate tenant registry secrets |

### Templates (YAML Manifests)

| Template File | Original Source | Description |
|---------------|-----------------|-------------|
| `ghcr-pull-secret.yaml.j2` | `infra/secrets/ksops/templates/ghcr-pull-secret.yaml` | GitHub Container Registry pull secret template |
| `ksops-generator.yaml.j2` | `infra/secrets/ksops/templates/ksops-generator.yaml` | KSOPS secret generator template |
| `kustomization.yaml.j2` | `infra/secrets/ksops/templates/kustomization.yaml` | Kustomization file for KSOPS secrets |
| `universal-secret-data.yaml.j2` | `infra/secrets/ksops/templates/universal-secret-data.yaml` | Universal secret data template |
| `universal-secret.yaml.j2` | `infra/secrets/ksops/templates/universal-secret.yaml` | Universal secret template |

## Helper Functions to Inline

The following helper functions from `zerotouch-platform/scripts/bootstrap/helpers/s3-helpers.sh` must be inlined into scripts that use them:

1. `configure_s3_credentials()` - Configure AWS CLI for S3 access
2. `s3_retrieve_age_key()` - Download and decrypt Age key from S3
3. `s3_backup_age_key()` - Encrypt and upload Age key to S3
4. `s3_age_key_exists()` - Check if Age key exists in S3

Scripts requiring these helpers:
- `08b-generate-age-keys.sh` - Uses all S3 helper functions
- `validate-age-keys-and-storage.sh` - Uses S3 retrieval functions
- `create-dot-env.sh` - Uses S3 retrieval functions
- `retrieve-age-key.sh` - Uses S3 retrieval functions

The `env-helpers.sh` functions (multi-line value handling) must be inlined into:
- `create-dot-env.sh` - Uses `write_env_var()` for multi-line secret handling

## Script Adaptation Guidelines

When adapting scripts from zerotouch-platform to ZTC adapter pattern:

1. **Replace CLI Arguments with Context File Reading**
   - Remove argument parsing (`while [[ $# -gt 0 ]]` loops)
   - Add context file validation and jq parsing
   - Map original arguments to context JSON keys

2. **Inline Helper Functions**
   - Copy helper function implementations directly into script
   - Remove `source` statements for external helpers
   - Preserve original function logic unchanged

3. **Preserve Core Business Logic**
   - Keep all API calls, kubectl commands, validation logic identical
   - Maintain error handling and exit codes
   - Preserve retry logic and timeouts

4. **Add Context File Validation**
   ```bash
   if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
       echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
       exit 1
   fi
   ```

5. **Reference Original Scripts**
   - For implementation details, refer to `zerotouch-platform/scripts/bootstrap/infra/secrets/`
   - Maintain same behavior and output as original scripts
   - Document any deviations from original implementation
