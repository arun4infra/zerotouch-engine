# Troubleshooting Guide

Common issues and solutions for ZTC.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Render Issues](#render-issues)
- [Validation Issues](#validation-issues)
- [Bootstrap Issues](#bootstrap-issues)
- [Adapter Issues](#adapter-issues)
- [Debug Techniques](#debug-techniques)

---

## Installation Issues

### Poetry Install Fails

**Symptom:**
```
poetry install fails with dependency resolution errors
```

**Solution:**
```bash
# Update Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Clear cache
poetry cache clear pypi --all

# Retry install
poetry install
```

### Python Version Mismatch

**Symptom:**
```
Python 3.11+ required
```

**Solution:**
```bash
# Check Python version
python --version

# Install Python 3.11+ (macOS)
brew install python@3.11

# Install Python 3.11+ (Linux)
apt-get install python3.11
```

---

## Render Issues

### "platform.yaml not found"

**Symptom:**
```
Error: platform.yaml not found
Run 'ztc init' to create platform configuration
```

**Solution:**
```bash
# Create platform.yaml manually or run init
ztc init

# Or create minimal platform.yaml
cat > platform.yaml <<EOF
adapters:
  cilium:
    version: v1.18.5
    bgp:
      enabled: false
EOF
```

### "No adapter outputs found in generated directory"

**Symptom:**
```
✗ Unexpected Error: No adapter outputs found in generated directory
```

**Cause:**
Some adapters (like Hetzner) don't generate manifest files - they only provide capability data.

**Solution:**
Ensure you have at least one adapter that generates manifests (Cilium or Talos):

```yaml
adapters:
  cilium:  # Generates manifests
    version: v1.18.5
    bgp:
      enabled: false
```

### "Adapter requires capability but no adapter provides it"

**Symptom:**
```
Error: Adapter 'talos' requires capability 'cloud-infrastructure' but no adapter provides it
```

**Cause:**
Missing upstream adapter that provides required capability.

**Solution:**
Add the required adapter:

```yaml
adapters:
  hetzner:  # Provides cloud-infrastructure
    version: v1.0.0
    api_token: your_token
    server_ips:
      - 192.168.1.1
  
  talos:  # Requires cloud-infrastructure
    version: v1.11.5
    # ...
```

### Render Hangs or Times Out

**Symptom:**
Render command hangs indefinitely.

**Solution:**
```bash
# Use debug mode to see where it's stuck
ztc render --debug

# Check workspace
ls -la .zerotouch-cache/workspace/

# Kill and retry
pkill -9 ztc
ztc render
```

### Template Rendering Errors

**Symptom:**
```
jinja2.exceptions.TemplateNotFound: cilium/manifests.yaml.j2
```

**Solution:**
- Ensure template exists in adapter's `templates/` directory
- Check template path uses adapter prefix: `adapter-name/template.j2`
- Verify adapter is properly registered

---

## Validation Issues

### "Lock file validation failed: platform.yaml hash mismatch"

**Symptom:**
```
✗ Validation failed: Lock file validation failed: platform.yaml hash mismatch

Help: Run 'ztc render' to regenerate artifacts and update the lock file
```

**Cause:**
`platform.yaml` was modified after rendering.

**Solution:**
```bash
# Re-render to update artifacts
ztc render

# Validate again
ztc validate
```

### "Lock file validation failed: artifacts hash mismatch"

**Symptom:**
```
✗ Validation failed: Lock file validation failed: artifacts hash mismatch
```

**Cause:**
Generated artifacts were manually modified.

**Solution:**
```bash
# Re-render to regenerate artifacts
ztc render

# Validate again
ztc validate
```

### Lock File Missing

**Symptom:**
```
Error: Lock file not found: platform/lock.json
```

**Solution:**
```bash
# Run render to create lock file
ztc render
```

---

## Bootstrap Issues

### "Required tool 'jq' not found in PATH"

**Symptom:**
```
✗ Runtime dependency error: Required tool 'jq' not found in PATH

Help: Install 'jq' before running this command
Install with: brew install jq (macOS) or apt-get install jq (Linux)
```

**Solution:**
```bash
# macOS
brew install jq yq kubectl

# Linux
apt-get install jq
snap install yq kubectl

# Verify installation
jq --version
yq --version
kubectl version --client
```

### Bootstrap Stage Fails

**Symptom:**
Bootstrap fails at specific stage.

**Solution:**
```bash
# Eject scripts for manual debugging
ztc eject --output debug-bootstrap

# Inspect failed stage
cd debug-bootstrap
cat README.md

# Check stage logs
cat logs/stage-name.log

# Execute stage manually
export ZTC_CONTEXT_FILE=context/stage-name.json
./scripts/adapter/stage-script.sh
```

### Stage Cache Issues

**Symptom:**
Bootstrap skips stages that should run.

**Solution:**
```bash
# Clear stage cache
rm -f .zerotouch-cache/bootstrap-stage-cache.json

# Re-run bootstrap
ztc bootstrap

# Or skip cache
ztc bootstrap --skip-cache
```

---

## Adapter Issues

### Adapter Not Discovered

**Symptom:**
```
Error: Adapter 'my-adapter' not found
```

**Solution:**
1. Ensure adapter has `adapter.yaml` file
2. Verify adapter is registered in `ztc/adapters/__init__.py`
3. Check adapter directory structure:
   ```
   ztc/adapters/my-adapter/
   ├── adapter.py
   ├── adapter.yaml
   └── config.py
   ```

### Configuration Validation Fails

**Symptom:**
```
pydantic.ValidationError: 1 validation error for MyAdapterConfig
```

**Solution:**
- Check `platform.yaml` has all required fields
- Verify field types match Pydantic model
- Check for typos in field names

**Example:**
```yaml
# ❌ Wrong
adapters:
  talos:
    version: v1.11.5
    # Missing required fields

# ✅ Correct
adapters:
  talos:
    version: v1.11.5
    factory_image_id: abc123
    cluster_name: my-cluster
    cluster_endpoint: 192.168.1.1:6443
    nodes:
      - name: cp01
        ip: 192.168.1.1
        role: controlplane
```

### Script Validation Fails

**Symptom:**
```
FileNotFoundError: Script 'install.sh' not found in package 'ztc.adapters.my_adapter.scripts'
```

**Solution:**
- Ensure script exists in correct directory
- Check `ScriptReference` package path is correct
- Verify script is included in package (not in `.gitignore`)

---

## Debug Techniques

### Enable Debug Mode

Preserve workspace on failure:

```bash
ztc render --debug
```

Workspace preserved at `.zerotouch-cache/workspace/`

### Inspect Workspace

```bash
# List workspace contents
ls -la .zerotouch-cache/workspace/

# View generated manifests
cat .zerotouch-cache/workspace/generated/cilium/manifests.yaml

# Check pipeline
cat .zerotouch-cache/workspace/pipeline.yaml
```

### Eject for Manual Execution

```bash
# Eject all scripts and context
ztc eject --output debug

# Inspect
cd debug
cat README.md

# Execute manually
export ZTC_CONTEXT_FILE=context/script-name.json
./scripts/adapter/script-name.sh
```

### Check Logs

```bash
# Bootstrap logs
cat .zerotouch-cache/bootstrap.log

# Stage-specific logs
cat .zerotouch-cache/logs/stage-name.log
```

### Verbose Output

```bash
# Run with verbose pytest output
poetry run pytest tests/integration/test_render_pipeline.py -vv

# Check test output
poetry run pytest tests/integration/ -v --tb=short
```

### Inspect Lock File

```bash
# View lock file
cat platform/lock.json | jq .

# Check platform hash
jq '.platform_hash' platform/lock.json

# Check artifacts hash
jq '.artifacts_hash' platform/lock.json

# Check adapter versions
jq '.adapters' platform/lock.json
```

### Validate Configuration

```bash
# Check YAML syntax
python -c "import yaml; yaml.safe_load(open('platform.yaml'))"

# Validate against schema (if available)
# poetry run ztc validate-config platform.yaml
```

### Clean State

```bash
# Remove all generated artifacts
rm -rf platform/generated/
rm -f platform/lock.json

# Remove cache
rm -rf .zerotouch-cache/

# Remove temp directories
ztc vacuum

# Re-render from scratch
ztc render
```

---

## Common Error Messages

### "This is an unexpected error. Please report this issue."

**Meaning:**
An unhandled exception occurred.

**Action:**
1. Enable debug mode: `ztc render --debug`
2. Check workspace: `.zerotouch-cache/workspace/`
3. Report issue with error details and workspace contents

### "Validation failed: drift detected"

**Meaning:**
Configuration or artifacts changed after rendering.

**Action:**
```bash
ztc render  # Re-render to sync
ztc validate
```

### "Capability validation failed"

**Meaning:**
Adapter dependency chain is broken.

**Action:**
- Check `adapter.yaml` provides/requires declarations
- Ensure all required capabilities are provided by other adapters
- Verify adapter execution order

---

## Getting Help

### Check Documentation

- [README.md](../README.md) - Installation and quick start
- [CLI_REFERENCE.md](CLI_REFERENCE.md) - Command reference
- [ADAPTER_DEVELOPMENT.md](ADAPTER_DEVELOPMENT.md) - Adapter development

### Run Tests

```bash
# All tests
poetry run pytest

# Specific test
poetry run pytest tests/integration/test_render_pipeline.py -v

# With coverage
poetry run pytest --cov=ztc tests/
```

### Enable Verbose Logging

```bash
# Set log level (if implemented)
export ZTC_LOG_LEVEL=DEBUG
ztc render
```

### Report Issues

When reporting issues, include:
1. ZTC version: `ztc version`
2. Python version: `python --version`
3. Operating system
4. Full error message
5. `platform.yaml` (redact sensitive data)
6. Steps to reproduce

---

## Performance Issues

### Slow Render

**Symptom:**
Render takes longer than expected.

**Possible Causes:**
- Large number of nodes in Talos config
- Network latency (if adapters make API calls)
- Slow disk I/O

**Solutions:**
```bash
# Use partial render for specific adapters
ztc render --partial cilium

# Check disk space
df -h

# Monitor resource usage
top
```

### High Memory Usage

**Symptom:**
ZTC consumes excessive memory.

**Solutions:**
- Reduce number of nodes in configuration
- Use streaming for large files
- Report issue if memory usage is unexpectedly high

---

## Platform-Specific Issues

### macOS

**Issue:** Permission denied on scripts

**Solution:**
```bash
chmod +x scripts/*.sh
```

**Issue:** Gatekeeper blocks execution

**Solution:**
```bash
xattr -d com.apple.quarantine ztc
```

### Linux

**Issue:** Missing dependencies

**Solution:**
```bash
# Install build dependencies
apt-get install build-essential python3-dev

# Install runtime dependencies
apt-get install jq
snap install yq kubectl
```

---

## Still Having Issues?

If you're still experiencing problems:

1. Clean state and retry:
   ```bash
   rm -rf platform/generated/ .zerotouch-cache/
   ztc render
   ```

2. Check for known issues in repository

3. Report issue with full details

4. Join community discussions (if available)
