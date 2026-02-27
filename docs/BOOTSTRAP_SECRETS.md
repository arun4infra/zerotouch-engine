# Bootstrap Secrets Setup

The bootstrap process requires decrypted secrets to execute stages. This document explains how to set up Age encryption keys for local development and CI/CD.

## Security Model

**Hybrid Approach:**
- **Local Dev**: Age key stored in `~/.ztp_cli/secrets`
- **CI/CD**: Age key injected via `SOPS_AGE_KEY` environment variable
- **Runtime**: Secrets decrypted once at bootstrap start, kept in memory only
- **Cleanup**: Secrets zeroed from memory after execution

**Principles:**
- ✅ Least persistence (no decrypted secrets on disk)
- ✅ Least exposure (secrets only in memory during execution)
- ✅ Industry-aligned (standard SOPS + Age workflow)

## Prerequisites

Install required tools:

```bash
# macOS
brew install sops age

# Linux
# Install from: https://github.com/getsops/sops
# Install from: https://github.com/FiloSottile/age
```

## Setup for Local Development

### Option 1: Retrieve from S3 (Recommended)

If your Age key is backed up in S3:

```bash
# 1. Create .env.local with S3 credentials
cat > .env.local <<EOF
DEV_HETZNER_S3_ENDPOINT=https://fsn1.your-objectstorage.com
DEV_HETZNER_S3_ACCESS_KEY=your-access-key
DEV_HETZNER_S3_SECRET_KEY=your-secret-key
DEV_HETZNER_S3_BUCKET=your-bucket
EOF

# 2. Retrieve Age key from S3
cd zerotouch-platform
ENV=dev ./scripts/bootstrap/infra/secrets/ksops/retrieve-age-key.sh

# 3. Save to Age key file
mkdir -p ~/.config/sops/age
echo "AGE-SECRET-KEY-1..." > ~/.ztp_cli/secrets
chmod 600 ~/.ztp_cli/secrets
```

### Option 2: Use Existing Key

If you already have the Age private key:

```bash
# Save to Age key file
mkdir -p ~/.config/sops/age
echo "AGE-SECRET-KEY-1..." > ~/.ztp_cli/secrets
chmod 600 ~/.ztp_cli/secrets
```

### Option 3: Environment Variable (Temporary)

For one-off runs without persisting the key:

```bash
export SOPS_AGE_KEY="AGE-SECRET-KEY-1..."
./ztc-new.py bootstrap
```

## Setup for CI/CD

Set the Age key as a secret in your CI/CD platform:

### GitHub Actions

```yaml
# .github/workflows/bootstrap.yml
env:
  SOPS_AGE_KEY: ${{ secrets.SOPS_AGE_KEY_DEV }}

steps:
  - name: Bootstrap cluster
    run: ./ztc-new.py bootstrap
```

**Add secret to GitHub:**
1. Go to: `https://github.com/your-org/your-repo/settings/secrets/actions`
2. Click: "New repository secret"
3. Name: `SOPS_AGE_KEY_DEV`
4. Value: `AGE-SECRET-KEY-1...`

### GitLab CI

```yaml
# .gitlab-ci.yml
variables:
  SOPS_AGE_KEY: $SOPS_AGE_KEY_DEV

bootstrap:
  script:
    - ./ztc-new.py bootstrap
```

**Add secret to GitLab:**
1. Go to: Settings → CI/CD → Variables
2. Add variable: `SOPS_AGE_KEY_DEV`
3. Type: Masked, Protected

## Verification

Test that secrets can be decrypted:

```bash
# Test SOPS decryption
sops -d platform/generated/argocd/k8/core/secrets/hcloud.secret.yaml

# Should output decrypted YAML with token visible
```

## Troubleshooting

### "Age private key not found"

**Symptom:**
```
Warning: Age private key not found. Secrets will not be available.
  Local dev: Place key in ~/.ztp_cli/secrets
  CI/CD: Set SOPS_AGE_KEY environment variable
```

**Solution:**
- Local: Follow "Setup for Local Development" above
- CI/CD: Ensure `SOPS_AGE_KEY` is set in your CI/CD secrets

### "Failed to decrypt secret"

**Symptom:**
```
Warning: Failed to decrypt hcloud.secret.yaml: ...
```

**Possible causes:**
1. Wrong Age key (doesn't match the recipient in the encrypted file)
2. Corrupted encrypted file
3. SOPS not installed

**Solution:**
```bash
# Check Age recipient in encrypted file
grep "recipient:" platform/generated/argocd/k8/core/secrets/hcloud.secret.yaml

# Verify your Age public key matches
age-keygen -y ~/.ztp_cli/secrets
```

### "SOPS not found"

**Solution:**
```bash
# macOS
brew install sops

# Linux
wget https://github.com/getsops/sops/releases/download/v3.8.1/sops-v3.8.1.linux.amd64
sudo mv sops-v3.8.1.linux.amd64 /usr/local/bin/sops
sudo chmod +x /usr/local/bin/sops
```

## Security Best Practices

1. **Never commit Age private keys** to version control
2. **Use different keys per environment** (dev/staging/prod)
3. **Rotate keys periodically** (re-encrypt secrets with new key)
4. **Limit key access** (only authorized personnel)
5. **Backup keys securely** (encrypted S3, password manager, vault)

## Key Rotation

When rotating Age keys:

```bash
# 1. Generate new Age key
age-keygen -o new-key.txt

# 2. Re-encrypt all secrets with new key
for file in platform/generated/argocd/k8/core/secrets/*.secret.yaml; do
  sops updatekeys -y "$file"
done

# 3. Update Age key file
mv new-key.txt ~/.ztp_cli/secrets

# 4. Backup new key to S3
# (Use your backup script)
```
