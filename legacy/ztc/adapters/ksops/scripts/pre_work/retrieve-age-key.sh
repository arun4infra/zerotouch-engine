#!/usr/bin/env bash
# Retrieve and decrypt Age private key from S3
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

echo "Retrieve Age Private Key from S3"
echo "================================="
echo ""

# Configure S3 credentials (function from s3-helpers.sh)
echo "Configuring S3 credentials..."
if ! configure_s3_credentials; then
    echo "ERROR: Failed to configure S3 credentials" >&2
    exit 1
fi
echo "✓ S3 credentials configured"
echo ""

# Check if age is installed
if ! command -v age &> /dev/null; then
    echo "ERROR: age not found" >&2
    echo "Install age: https://github.com/FiloSottile/age" >&2
    exit 1
fi

# Retrieve Age key from S3
echo "Retrieving Age private key from S3..."
if ! AGE_PRIVATE_KEY=$(s3_retrieve_age_key); then
    echo "ERROR: Failed to retrieve Age key from S3" >&2
    echo "Run setup-env-secrets.sh first" >&2
    exit 1
fi

# Trim whitespace and validate
AGE_PRIVATE_KEY=$(echo "$AGE_PRIVATE_KEY" | tr -d '[:space:]' | grep -o 'AGE-SECRET-KEY-1[A-Z0-9]*')

if [ -z "$AGE_PRIVATE_KEY" ]; then
    echo "ERROR: Invalid Age private key format" >&2
    exit 1
fi

echo "✓ Age private key retrieved"
echo ""

# Display result
echo "Age Private Key"
echo "==============="
echo ""
echo "$AGE_PRIVATE_KEY"
echo ""
