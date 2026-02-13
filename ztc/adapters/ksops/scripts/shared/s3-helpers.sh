#!/bin/bash
# S3 Helper Functions for Hetzner Object Storage
# Shared functions for S3 operations across scripts
#
# META_REQUIRE: S3_ACCESS_KEY (env)
# META_REQUIRE: S3_SECRET_KEY (env)
# META_REQUIRE: s3_endpoint (context)
# META_REQUIRE: s3_region (context)
# META_REQUIRE: s3_bucket_name (context)
#
# Note: This file will be inlined into scripts via # INCLUDE: markers
# during get_embedded_script() execution

# Configure S3 credentials from environment and context
# Reads S3 endpoint/region/bucket from context file
# Reads S3 credentials from environment variables
configure_s3_credentials() {
    # Read from context file
    export S3_ENDPOINT=$(jq -r '.s3_endpoint' "$ZTC_CONTEXT_FILE")
    export AWS_DEFAULT_REGION=$(jq -r '.s3_region' "$ZTC_CONTEXT_FILE")
    export S3_BUCKET=$(jq -r '.s3_bucket_name' "$ZTC_CONTEXT_FILE")
    
    # Read credentials from environment
    export AWS_ACCESS_KEY_ID="${S3_ACCESS_KEY:-}"
    export AWS_SECRET_ACCESS_KEY="${S3_SECRET_KEY:-}"
    
    # Validate required variables
    if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ] || \
       [ -z "$S3_ENDPOINT" ] || [ -z "$AWS_DEFAULT_REGION" ] || [ -z "$S3_BUCKET" ]; then
        return 1
    fi
    
    return 0
}

# Download Age key from S3
# Returns: 0 if successful, 1 if not found or error
# Outputs: AGE_PRIVATE_KEY to stdout if successful
s3_retrieve_age_key() {
    local temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" RETURN
    
    # Download ACTIVE backup files (suppress all output)
    if ! aws s3 cp "s3://${S3_BUCKET}/age-keys/ACTIVE-age-key-encrypted.txt" \
        "$temp_dir/encrypted.txt" \
        --endpoint-url "$S3_ENDPOINT" \
        --cli-connect-timeout 10 \
        --quiet >/dev/null 2>&1; then
        return 1
    fi
    
    if ! aws s3 cp "s3://${S3_BUCKET}/age-keys/ACTIVE-recovery-key.txt" \
        "$temp_dir/recovery.key" \
        --endpoint-url "$S3_ENDPOINT" \
        --cli-connect-timeout 10 \
        --quiet >/dev/null 2>&1; then
        return 1
    fi
    
    # Decrypt Age key
    local age_private_key
    if ! age_private_key=$(age -d -i "$temp_dir/recovery.key" "$temp_dir/encrypted.txt" 2>/dev/null); then
        return 1
    fi
    
    echo "$age_private_key"
    return 0
}

# Upload Age key to S3
# Args: $1 = AGE_PRIVATE_KEY, $2 = RECOVERY_PRIVATE_KEY, $3 = RECOVERY_PUBLIC_KEY
# Returns: 0 if successful, 1 if error
s3_backup_age_key() {
    local age_private_key="$1"
    local recovery_private_key="$2"
    local recovery_public_key="$3"
    
    if [ -z "$age_private_key" ] || [ -z "$recovery_private_key" ]; then
        echo "Error: Missing required parameters" >&2
        return 1
    fi
    
    local temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" RETURN
    
    # Encrypt Age private key with recovery key
    local encrypted_backup
    if ! encrypted_backup=$(echo "$age_private_key" | age -r "$recovery_public_key" -a 2>&1); then
        echo "Error: Failed to encrypt Age key" >&2
        return 1
    fi
    
    echo "$encrypted_backup" > "$temp_dir/age-key-encrypted.txt"
    echo "$recovery_private_key" > "$temp_dir/recovery-key.txt"
    
    local timestamp=$(date +%Y%m%d-%H%M%S)
    
    # Check if bucket exists, create if not
    if ! aws s3 ls "s3://$S3_BUCKET" --endpoint-url "$S3_ENDPOINT" --cli-connect-timeout 10 &>/dev/null; then
        if ! aws s3 mb "s3://$S3_BUCKET" --endpoint-url "$S3_ENDPOINT" --region "$AWS_DEFAULT_REGION" --cli-connect-timeout 10 2>&1 | grep -v "BucketAlreadyExists"; then
            if ! aws s3 ls "s3://$S3_BUCKET" --endpoint-url "$S3_ENDPOINT" --cli-connect-timeout 10 &>/dev/null; then
                echo "Error: Failed to create bucket" >&2
                return 1
            fi
        fi
    fi
    
    # Upload timestamped backups
    if ! aws s3 cp "$temp_dir/age-key-encrypted.txt" \
        "s3://$S3_BUCKET/age-keys/$timestamp-age-key-encrypted.txt" \
        --endpoint-url "$S3_ENDPOINT" \
        --cli-connect-timeout 10 \
        --cli-read-timeout 30 2>&1; then
        echo "Error: Failed to upload encrypted Age key" >&2
        return 1
    fi
    
    if ! aws s3 cp "$temp_dir/recovery-key.txt" \
        "s3://$S3_BUCKET/age-keys/$timestamp-recovery-key.txt" \
        --endpoint-url "$S3_ENDPOINT" \
        --cli-connect-timeout 10 \
        --cli-read-timeout 30 2>&1; then
        echo "Error: Failed to upload recovery key" >&2
        return 1
    fi
    
    # Mark as active
    if ! aws s3 cp "$temp_dir/age-key-encrypted.txt" \
        "s3://$S3_BUCKET/age-keys/ACTIVE-age-key-encrypted.txt" \
        --endpoint-url "$S3_ENDPOINT" \
        --cli-connect-timeout 10 \
        --cli-read-timeout 30 2>&1; then
        echo "Error: Failed to mark active encrypted key" >&2
        return 1
    fi
    
    if ! aws s3 cp "$temp_dir/recovery-key.txt" \
        "s3://$S3_BUCKET/age-keys/ACTIVE-recovery-key.txt" \
        --endpoint-url "$S3_ENDPOINT" \
        --cli-connect-timeout 10 \
        --cli-read-timeout 30 2>&1; then
        echo "Error: Failed to mark active recovery key" >&2
        return 1
    fi
    
    return 0
}

# Check if Age key exists in S3
# Returns: 0 if exists, 1 if not found
s3_age_key_exists() {
    aws s3 ls "s3://${S3_BUCKET}/age-keys/ACTIVE-age-key-encrypted.txt" \
        --endpoint-url "$S3_ENDPOINT" \
        --cli-connect-timeout 10 &>/dev/null
    return $?
}
