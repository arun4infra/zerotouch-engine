## Design Improvements

### 1. Script Contract Validation

**Problem**: Loose contract between Python config and bash scripts. Field name mismatches (`tenant_repo_name` vs `.repo_name`) only caught at runtime.

**Solution**: Add `META_REQUIRE` headers to bash scripts and validate during unit tests.

```bash
#!/usr/bin/env bash
# META_REQUIRE: s3_access_key
# META_REQUIRE: s3_bucket_name

S3_ACCESS_KEY=$(jq -r '.s3_access_key' "$ZTC_CONTEXT_FILE")
```

```python
def test_script_contract_adherence():
    """Ensure context_data matches script requirements"""
    adapter = MyAdapter(mock_config)
    for ref in adapter.bootstrap_scripts():
        script_content = adapter.get_embedded_script(ref.resource)
        required_keys = parse_meta_requirements(script_content)
        assert required_keys.issubset(ref.context_data.keys())
```

### 2. Lazy CLI Loading

**Problem**: Instantiating all adapters on CLI startup causes lag with 19+ adapters.

**Solution**: Use static metadata from `adapter.yaml` for CLI registration, defer instantiation until command invoked.

```python
# ztc/cli.py
if issubclass(adapter_class, CLIExtension):
    # Read category from adapter.yaml, don't instantiate
    category = adapter_class.get_static_cli_category()
    app.add_typer(..., name=category, callback=lazy_loader(adapter_class))
```

### 3. Explicit Manifest Paths

**Problem**: `manifests: Dict[str, str]` with filename keys allows collisions when multiple adapters write `kustomization.yaml`.

**Solution**: Enforce relative paths in manifest keys to control directory structure.

```python
# Current (collision risk)
manifests = {"kustomization.yaml": content}

# Improved (explicit path)
manifests = {"secrets/overlays/main/kustomization.yaml": content}
```

Engine writes to `platform/generated/{adapter_name}/{relative_path}` or adapter controls full relative path for complex structures (Kustomize overlays).

### 4. Hybrid Context/Env Strategy

**Problem**: Writing secrets (`s3_secret_key`, `github_app_private_key`) to JSON context files persists sensitive data on disk.

**Solution**: Add `secret_env_vars` field to `ScriptReference` for ephemeral secret passing.

```python
@dataclass
class ScriptReference:
    package: str
    resource: str
    context_data: Dict = None      # Non-secret configuration
    secret_env_vars: Dict = None   # Secrets passed via environment

ScriptReference(
    package="ztc.adapters.my_adapter.scripts",
    resource="bootstrap.sh",
    context_data={
        "s3_bucket_name": "my-bucket",  # Safe to write to disk
        "s3_region": "us-east-1"
    },
    secret_env_vars={
        "S3_SECRET_KEY": config.s3_secret_key.get_secret_value(),  # Passed to subprocess only
        "API_TOKEN": config.api_token.get_secret_value()
    }
)
```

Scripts read secrets from environment, configuration from context file:

```bash
# Read configuration from context file
S3_BUCKET=$(jq -r '.s3_bucket_name' "$ZTC_CONTEXT_FILE")

# Read secrets from environment
S3_SECRET_KEY="${S3_SECRET_KEY:?S3_SECRET_KEY not set}"
```

### 4a. SecretStr for Config Models

**Problem**: Pydantic's default `__repr__` includes field values. If adapter config is dumped to logs during exceptions, secrets leak.

**Solution**: Use Pydantic `SecretStr` for sensitive fields to mask them in logs.

```python
from pydantic import BaseModel, SecretStr

class MyAdapterConfig(BaseModel):
    # Sensitive fields use SecretStr
    s3_access_key: SecretStr
    s3_secret_key: SecretStr
    api_token: SecretStr
    github_app_private_key: SecretStr
    
    # Non-sensitive fields use regular types
    s3_bucket_name: str
    s3_region: str
    s3_endpoint: str

# Usage: Must call .get_secret_value() to access
config = MyAdapterConfig(**user_input)
secret_value = config.s3_secret_key.get_secret_value()

# Logging automatically masks secrets
print(config)  # Shows: s3_secret_key=SecretStr('**********')
logger.error(f"Config: {config}")  # Secrets remain masked
```

**Integration with secret_env_vars:**

```python
ScriptReference(
    package="ztc.adapters.my_adapter.scripts",
    resource="bootstrap.sh",
    context_data={
        "s3_bucket_name": config.s3_bucket_name,
        "s3_region": config.s3_region
    },
    secret_env_vars={
        # Explicitly extract secret values
        "S3_SECRET_KEY": config.s3_secret_key.get_secret_value(),
        "API_TOKEN": config.api_token.get_secret_value()
    }
)
```

**Benefits:**
- Secrets masked in logs, error messages, debug output, exception tracebacks
- Explicit `.get_secret_value()` call makes secret access visible in code reviews
- Prevents accidental secret leakage via `print()`, `str()`, or logging
- Works seamlessly with `secret_env_vars` pattern

### 5. Pre-Flight Health Checks

**Problem**: Connectivity failures (S3 unreachable, API down) caught late in bootstrap pipeline.

**Solution**: Add optional `check_health()` method to `PlatformAdapter` for pre-flight validation.

```python
class MyAdapter(PlatformAdapter):
    def check_health(self) -> None:
        """Optional pre-flight connectivity check
        
        Uses localized imports to avoid CLI startup penalty.
        """
        # Localized import - only loaded when health check runs
        import boto3
        from botocore.exceptions import ClientError
        
        config = MyAdapterConfig(**self.config)
        
        try:
            client = boto3.client(
                's3',
                endpoint_url=config.s3_endpoint,
                aws_access_key_id=config.s3_access_key.get_secret_value(),
                aws_secret_access_key=config.s3_secret_key.get_secret_value()
            )
            client.head_bucket(Bucket=config.s3_bucket_name)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                raise PreFlightError(
                    f"S3 bucket '{config.s3_bucket_name}' not found",
                    hint="Create bucket or check bucket name"
                )
            elif error_code == '403':
                raise PreFlightError(
                    f"Access denied to bucket '{config.s3_bucket_name}'",
                    hint="Verify S3 credentials have read/write permissions"
                )
            else:
                raise PreFlightError(f"S3 connectivity check failed: {e}")
        except Exception as e:
            raise PreFlightError(
                f"Cannot reach S3 endpoint {config.s3_endpoint}: {e}",
                hint="Check network connectivity and endpoint URL"
            )
```

Engine calls `check_health()` before render/bootstrap if implemented. Not mandatory (supports offline/air-gapped scenarios).

### 5a. Lazy Imports for Heavy Libraries

**Problem**: Heavy libraries (`boto3`, `kubernetes`, `azure-sdk`) imported at module level slow CLI startup. Running `ztc --help` shouldn't load AWS SDK.

**Solution**: Use localized imports inside methods, never at module level.

```python
# BAD: Module-level import
import boto3  # Loaded on every CLI invocation

class MyAdapter(PlatformAdapter):
    def check_health(self):
        client = boto3.client('s3')  # Already loaded

# GOOD: Localized import
class MyAdapter(PlatformAdapter):
    def check_health(self):
        import boto3  # Only loaded when method called
        client = boto3.client('s3')
```

**Verification Test:**

```python
def test_no_heavy_imports_on_module_load():
    """Ensure heavy libraries not loaded during adapter import"""
    import sys
    
    # Clear any existing imports
    for mod in list(sys.modules.keys()):
        if 'boto' in mod or 'kubernetes' in mod:
            del sys.modules[mod]
    
    # Import adapter module
    from ztc.adapters.my_adapter import adapter
    
    # Verify heavy libs not loaded
    assert 'boto3' not in sys.modules
    assert 'botocore' not in sys.modules
    assert 'kubernetes' not in sys.modules
```

**Benefits:**
- Fast CLI startup (`ztc --help`, `ztc version`)
- Heavy libs only loaded when actually needed
- Critical for 19+ adapter catalog

### 6. Protocol-Based CLI Enforcement

**Problem**: No compile-time guarantee that adapters implementing `CLIExtension` provide required methods with correct signatures.

**Solution**: Define `CLIExtension` as a Protocol (structural subtyping) instead of a mixin class.

```python
# ztc/adapters/base.py
from typing import Protocol, runtime_checkable
import typer

@runtime_checkable
class CLIExtension(Protocol):
    """Protocol for adapters providing CLI commands
    
    Adapters implementing this protocol must provide:
    - get_cli_category() as static method returning category name
    - get_cli_app() as instance method returning Typer app
    """
    
    @staticmethod
    def get_cli_category() -> str:
        """Return CLI category name (e.g., 'secret', 'network', 'storage')
        
        Static method allows CLI registration without adapter instantiation.
        Maps selection_group to user-facing category name.
        """
        ...
    
    def get_cli_app(self) -> typer.Typer:
        """Return Typer app with registered commands
        
        Commands registered here appear under 'ztc {category}' namespace.
        All adapters in same category must implement compatible commands.
        """
        ...
```

**Adapter Implementation:**

```python
class MyAdapter(PlatformAdapter):
    """Adapter with CLI commands"""
    
    @staticmethod
    def get_cli_category() -> str:
        return "secret"
    
    def get_cli_app(self) -> typer.Typer:
        app = typer.Typer(help="Secrets management")
        app.command(name="init")(self.init_command)
        return app
    
    def init_command(self, env: str):
        """Initialize secrets"""
        pass
```

**CLI Registration (ztc/cli.py):**

```python
# Discover adapters with CLI extensions
for adapter_class in registry.get_all_adapters():
    if isinstance(adapter_class, type) and issubclass(adapter_class, CLIExtension):
        # Static method - no instantiation needed
        category = adapter_class.get_cli_category()
        
        # Lazy loader - instantiate only when command invoked
        def make_loader(cls):
            def loader():
                instance = cls(config={}, jinja_env=None)
                return instance.get_cli_app()
            return loader
        
        app.add_typer(make_loader(adapter_class)(), name=category)
```

**Benefits:**
- Type checker validates method signatures at development time
- Runtime validation via `isinstance(adapter_class, CLIExtension)`
- No inheritance required - duck typing with type safety
- Clear contract for CLI-enabled adapters

### 7. Output Sanitization for Security

**Problem**: `AdapterOutput.data` and `AdapterOutput.env_vars` are untyped `Dict[str, Any]`. Developers might accidentally add sensitive fields (secrets) during debugging, causing credential leakage in logs.

**Solution**: Use typed Pydantic models for adapter output to prevent secret leakage.

```python
from pydantic import BaseModel, field_validator, SecretStr
from typing import Dict, Any

class AdapterOutputData(BaseModel):
    """Typed model for adapter output data
    
    Only non-sensitive metadata allowed. Secrets forbidden.
    """
    
    class Config:
        extra = "forbid"  # Reject unknown fields
    
    @field_validator('*')
    @classmethod
    def no_secret_str(cls, v):
        """Reject SecretStr types in output"""
        if isinstance(v, SecretStr):
            raise ValueError(
                "SecretStr not allowed in adapter output. "
                "Use secret_env_vars in ScriptReference instead."
            )
        return v

# Adapter-specific output models
class KSOPSOutputData(AdapterOutputData):
    """KSOPS adapter output metadata"""
    s3_bucket: str
    tenant_org: str
    tenant_repo: str
    # Secrets NOT allowed here

# Usage in adapter
async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
    config = KSOPSConfig(**self.config)
    
    output_data = KSOPSOutputData(
        s3_bucket=config.s3_bucket_name,  # OK - public metadata
        tenant_org=config.tenant_org_name,
        tenant_repo=config.tenant_repo_name
        # config.s3_secret_key NOT allowed - would fail validation
    )
    
    return AdapterOutput(
        manifests={},
        stages=[],
        env_vars={},
        capabilities={"secrets-management": secrets_capability},
        data=output_data.model_dump()
    )
```

**Benefits:**
- Prevents accidental secret leakage in adapter output
- Type-safe data transfer between adapters
- Explicit validation at output boundary
- "Secure by default" architecture

### 8. Atomic Scripts - No Inter-Script Dependencies

**Problem**: Scripts calling other scripts (e.g., `setup-env-secrets.sh` calls `08b-generate-age-keys.sh`) creates fragile dependencies on directory layout and execution context.

**Anti-Pattern:**

```bash
# BAD: setup-env-secrets.sh calling another script
./08b-generate-age-keys.sh "$ENV"
```

**Solution**: Scripts must be atomic. Adapter orchestrates multi-step workflows via sequential `ScriptReference` calls.

```python
# GOOD: Adapter orchestrates script sequence
def init_secrets_command(self, env: str):
    """Initialize environment secrets"""
    executor = ScriptExecutor()
    
    # Step 1: Generate Age keys
    keys_ref = ScriptReference(
        package="ztc.adapters.ksops.scripts",
        resource=KSOPSScripts.GENERATE_AGE_KEYS,
        context_data={"env": env, ...}
    )
    executor.execute(keys_ref)
    
    # Step 2: Setup environment secrets
    setup_ref = ScriptReference(
        package="ztc.adapters.ksops.scripts",
        resource=KSOPSScripts.SETUP_ENV,
        context_data={"env": env, ...}
    )
    executor.execute(setup_ref)
```

**Benefits:**
- Scripts remain portable and testable in isolation
- No assumptions about directory layout or sibling scripts
- Adapter becomes single source of truth for execution order
- Easier to refactor, reorder, or parallelize operations

**Rule**: If a script needs another script's functionality, refactor into:
1. Shared helper function (inlined via `# INCLUDE`)
2. Sequential adapter calls (orchestration in Python)
3. Never script-to-script calls
