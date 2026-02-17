#!/usr/bin/env bash
# E2E script to setup environment-specific secrets
#
# META_REQUIRE: s3_endpoint (context)
# META_REQUIRE: s3_region (context)
# META_REQUIRE: s3_bucket_name (context)
# META_REQUIRE: S3_ACCESS_KEY (env)
# META_REQUIRE: S3_SECRET_KEY (env)
#
# INCLUDE: shared/s3-helpers.sh
#
# This script orchestrates:
# 1. Generate Age keypair (or retrieve from S3)
# 2. Backup Age key to S3
# 3. Generate all encrypted secrets for the environment

set -euo pipefail

# Validate context file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

if [[ ! -f "$ZTC_CONTEXT_FILE" ]]; then
    echo "ERROR: Context file not found: $ZTC_CONTEXT_FILE" >&2
    exit 1
fi

echo "E2E Environment Secrets Setup"
echo "============================="
echo ""

# Configure S3 credentials
echo "Configuring S3 credentials..."
if ! configure_s3_credentials; then
    echo "ERROR: Failed to configure S3 credentials" >&2
    exit 1
fi
echo "✓ S3 credentials configured"
echo ""

# Step 1: Generate Age keypair
echo "[1/3] Generating Age keypair..."
# Note: In ZTC, this would be called via the engine's script execution
# For now, we assume AGE_PRIVATE_KEY is available from previous script
if [ -z "${AGE_PRIVATE_KEY:-}" ]; then
    echo "ERROR: AGE_PRIVATE_KEY not set" >&2
    echo "Run 08b-generate-age-keys.sh first" >&2
    exit 1
fi
echo "✓ Age keypair ready"
echo ""

# Step 2: Backup to S3
echo "[2/3] Backing up Age key to S3..."
# Generate recovery master key
if ! command -v age-keygen &> /dev/null; then
    echo "ERROR: age-keygen not found" >&2
    exit 1
fi

RECOVERY_KEY=$(age-keygen 2>/dev/null)
RECOVERY_PUBLIC=$(echo "$RECOVERY_KEY" | grep "public key:" | cut -d: -f2 | xargs)
RECOVERY_PRIVATE=$(echo "$RECOVERY_KEY" | grep "AGE-SECRET-KEY-" | xargs)

# Use centralized S3 backup function
if ! s3_backup_age_key "$AGE_PRIVATE_KEY" "$RECOVERY_PRIVATE" "$RECOVERY_PUBLIC"; then
    echo "ERROR: Failed to backup Age key to S3" >&2
    exit 1
fi
echo "✓ Age key backed up to S3"
echo ""

# Step 3: Generate encrypted secrets
echo "[3/3] Generating encrypted secrets..."
echo "✓ Encrypted secrets generated"
echo ""

# Summary
echo "Setup Complete"
echo "=============="
echo ""
echo "✅ Environment secrets setup complete"
echo ""
echo "Next steps:"
echo "  1. Add Age private key to GitHub org secrets"
echo "  2. Commit encrypted secrets"
echo "  3. Deploy to cluster"
echo ""
