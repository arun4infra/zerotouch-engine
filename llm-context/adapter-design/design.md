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
        "S3_SECRET_KEY": config.s3_secret_key,  # Passed to subprocess only
        "API_TOKEN": config.api_token
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

### 5. Pre-Flight Health Checks

**Problem**: Connectivity failures (S3 unreachable, API down) caught late in bootstrap pipeline.

**Solution**: Add optional `check_health()` method to `PlatformAdapter` for pre-flight validation.

```python
class MyAdapter(PlatformAdapter):
    def check_health(self) -> None:
        """Optional pre-flight connectivity check"""
        import boto3
        client = boto3.client('s3', 
            endpoint_url=self.config['s3_endpoint'],
            aws_access_key_id=self.config['s3_access_key'])
        try:
            client.head_bucket(Bucket=self.config['s3_bucket_name'])
        except Exception as e:
            raise PreFlightError(f"S3 unreachable: {e}")
```

Engine calls `check_health()` before render/bootstrap if implemented. Not mandatory (supports offline/air-gapped scenarios).
