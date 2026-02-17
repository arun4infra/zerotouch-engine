#!/usr/bin/env bash
# Backup Age Private Key to Hetzner Object Storage
#
# META_REQUIRE: s3_endpoint (context)
# META_REQUIRE: s3_region (context)
# META_REQUIRE: s3_bucket_name (context)
# META_REQUIRE: S3_ACCESS_KEY (env)
# META_REQUIRE: S3_SECRET_KEY (env)
# META_REQUIRE: AGE_PRIVATE_KEY (env)
#
# INCLUDE: shared/s3-helpers.sh

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

echo "Backup Age Key to Hetzner Object Storage"
echo "========================================="
echo ""

# Validate AGE_PRIVATE_KEY
if [ -z "${AGE_PRIVATE_KEY:-}" ]; then
    echo "ERROR: AGE_PRIVATE_KEY not set" >&2
    echo "Run 08b-generate-age-keys.sh first" >&2
    exit 1
fi

# Check if age is installed
if ! command -v age &> /dev/null; then
    echo "ERROR: age not found" >&2
    echo "Install age: https://github.com/FiloSottile/age" >&2
    exit 1
fi

# Check if age-keygen is installed
if ! command -v age-keygen &> /dev/null; then
    echo "ERROR: age-keygen not found" >&2
    echo "Install age: https://github.com/FiloSottile/age" >&2
    exit 1
fi

# Check if aws CLI is installed
if ! command -v aws &> /dev/null; then
    echo "ERROR: AWS CLI not found" >&2
    echo "Install AWS CLI: https://aws.amazon.com/cli/" >&2
    exit 1
fi

# Configure S3 credentials (function from s3-helpers.sh)
echo "Configuring S3 credentials..."
if ! configure_s3_credentials; then
    echo "ERROR: Failed to configure S3 credentials" >&2
    exit 1
fi

echo "✓ Prerequisites validated"
echo ""

# Generate recovery master key
echo "Generating recovery master key..."
RECOVERY_KEY=$(age-keygen 2>/dev/null)
RECOVERY_PUBLIC=$(echo "$RECOVERY_KEY" | grep "public key:" | cut -d: -f2 | xargs)
RECOVERY_PRIVATE=$(echo "$RECOVERY_KEY" | grep "AGE-SECRET-KEY-" | xargs)

echo "✓ Recovery master key generated"
echo "Recovery public key: $RECOVERY_PUBLIC"
echo ""

# Use centralized S3 backup function
echo "Backing up Age key to S3..."
if ! s3_backup_age_key "$AGE_PRIVATE_KEY" "$RECOVERY_PRIVATE" "$RECOVERY_PUBLIC"; then
    echo "ERROR: Failed to backup Age key to S3" >&2
    exit 1
fi

# Export recovery key for in-cluster backup
export RECOVERY_PRIVATE_KEY="$RECOVERY_PRIVATE"

echo ""
echo "Backup Summary"
echo "=============="
echo ""
echo "✓ Age key backed up to Hetzner Object Storage"
echo "✓ Location: s3://$S3_BUCKET/age-keys/ACTIVE-*"
echo ""
echo "CRITICAL: Store recovery key securely offline"
echo "Recovery public key: $RECOVERY_PUBLIC"
echo ""
echo "To recover Age key (using active markers):"
echo "  1. Download: aws s3 cp s3://$S3_BUCKET/age-keys/ACTIVE-recovery-key.txt recovery.key --endpoint-url $S3_ENDPOINT"
echo "  2. Download: aws s3 cp s3://$S3_BUCKET/age-keys/ACTIVE-age-key-encrypted.txt encrypted.txt --endpoint-url $S3_ENDPOINT"
echo "  3. Decrypt: age -d -i recovery.key encrypted.txt"
echo ""
