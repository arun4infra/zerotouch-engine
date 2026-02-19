#!/usr/bin/env bash
# Generate Age keypair for SOPS encryption
#
# META_REQUIRE: s3_endpoint (context)
# META_REQUIRE: s3_region (context)
# META_REQUIRE: s3_bucket_name (context)
# META_REQUIRE: S3_ACCESS_KEY (env)
# META_REQUIRE: S3_SECRET_KEY (env)
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

echo "Age Keypair Generation for SOPS Encryption"
echo "=========================================="
echo ""

# Check if age-keygen is installed
if ! command -v age-keygen &> /dev/null; then
    echo "ERROR: age-keygen not found" >&2
    echo "Install age: https://github.com/FiloSottile/age" >&2
    exit 1
fi

echo "✓ age-keygen found"
echo ""

# Configure S3 credentials (function from s3-helpers.sh)
echo "Configuring S3 credentials..."
if ! configure_s3_credentials; then
    echo "ERROR: Failed to configure S3 credentials" >&2
    exit 1
fi
echo "✓ S3 credentials configured"
echo ""

# Check if Age key exists in S3
echo "Checking S3 for existing Age key..."
if s3_age_key_exists; then
    echo "⚠ Existing Age key found in S3"
    echo "Retrieving existing Age key to maintain secret decryption..."
    
    # Retrieve Age key from S3
    if ! AGE_PRIVATE_KEY=$(s3_retrieve_age_key); then
        echo "ERROR: Failed to retrieve Age key from S3" >&2
        exit 1
    fi
    
    # Trim whitespace
    AGE_PRIVATE_KEY=$(echo "$AGE_PRIVATE_KEY" | tr -d '[:space:]' | grep -o 'AGE-SECRET-KEY-1[A-Z0-9]*')
    
    if [[ ! "$AGE_PRIVATE_KEY" =~ ^AGE-SECRET-KEY-1 ]]; then
        echo "ERROR: Invalid Age private key format from S3" >&2
        exit 1
    fi
    
    # Derive public key from private key
    AGE_PUBLIC_KEY=$(echo "$AGE_PRIVATE_KEY" | age-keygen -y 2>/dev/null)
    
    if [ -z "$AGE_PUBLIC_KEY" ]; then
        echo "ERROR: Failed to derive public key from existing private key" >&2
        exit 1
    fi
    
    echo "✓ Existing Age key retrieved from S3"
    echo ""
else
    echo "No existing Age key in S3, generating new keypair..."

    # Generate keypair and capture output
    KEYGEN_OUTPUT=$(age-keygen 2>&1)

    # Extract public key (format: # public key: age1...)
    AGE_PUBLIC_KEY=$(echo "$KEYGEN_OUTPUT" | grep "# public key:" | sed 's/# public key: //')

    # Extract private key (format: AGE-SECRET-KEY-1...)
    AGE_PRIVATE_KEY=$(echo "$KEYGEN_OUTPUT" | grep "^AGE-SECRET-KEY-1" | head -n 1)

    # Validate keys were generated
    if [ -z "$AGE_PUBLIC_KEY" ]; then
        echo "ERROR: Failed to generate public key" >&2
        exit 1
    fi

    if [ -z "$AGE_PRIVATE_KEY" ]; then
        echo "ERROR: Failed to generate private key" >&2
        exit 1
    fi

    echo "✓ Age keypair generated successfully"
    echo ""
    
    # Auto-backup to S3
    echo "Backing up new Age key to S3..."
    
    # Generate recovery master key
    RECOVERY_KEY=$(age-keygen 2>/dev/null)
    RECOVERY_PUBLIC=$(echo "$RECOVERY_KEY" | grep "public key:" | cut -d: -f2 | xargs)
    RECOVERY_PRIVATE=$(echo "$RECOVERY_KEY" | grep "AGE-SECRET-KEY-" | xargs)
    
    # Use centralized S3 backup function
    if ! s3_backup_age_key "$AGE_PRIVATE_KEY" "$RECOVERY_PRIVATE" "$RECOVERY_PUBLIC"; then
        echo "ERROR: Failed to backup Age key to S3" >&2
        exit 1
    fi
    
    echo "✓ Age key backed up to S3"
    echo "CRITICAL: Store recovery key securely offline"
    echo "Recovery public key: $RECOVERY_PUBLIC"
    echo ""
fi

# Export keys to environment variables
export AGE_PUBLIC_KEY
export AGE_PRIVATE_KEY

echo "Generated Keys"
echo "=============="
echo ""
echo "Public Key:"
echo "  $AGE_PUBLIC_KEY"
echo ""
echo "Private Key:"
echo "  $AGE_PRIVATE_KEY"
echo ""

echo "✓ AGE_PUBLIC_KEY exported"
echo "✓ AGE_PRIVATE_KEY exported"
echo ""
