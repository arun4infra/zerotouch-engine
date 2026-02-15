#!/bin/bash
# S3 Helper Functions for Object Storage
# Shared functions for S3 operations across KSOPS scripts
#
# Usage: source this file in scripts that need S3 access
#   source "$SCRIPT_DIR/../helpers/s3-helpers.sh"

# Configure S3 credentials from context and environment
# Expects: S3_ACCESS_KEY, S3_SECRET_KEY env vars + context file with endpoint/region/bucket
configure_s3_credentials() {
    # Validate secret environment variables
    if [ -z "${S3_ACCESS_KEY:-}" ]; then
        echo "Error: S3_ACCESS_KEY environment variable not set" >&2
        return 1
    fi
    
    if [ -z "${S3_SECRET_KEY:-}" ]; then
        echo "Error: S3_SECRET_KEY environment variable not set" >&2
        return 1
    fi
    
    # Validate context file
    if [ -z "${ZTC_CONTEXT_FILE:-}" ] || [ ! -f "$ZTC_CONTEXT_FILE" ]; then
        echo "Error: ZTC_CONTEXT_FILE not set or file not found" >&2
        return 1
    fi
    
    # Check for jq
    if ! command -v jq &> /dev/null; then
        echo "Error: jq not found (required for JSON parsing)" >&2
        return 1
    fi
    
    # Read context data
    local s3_endpoint=$(jq -r '.s3_endpoint' "$ZTC_CONTEXT_FILE")
    local s3_region=$(jq -r '.s3_region' "$ZTC_CONTEXT_FILE")
    local s3_bucket=$(jq -r '.s3_bucket_name' "$ZTC_CONTEXT_FILE")
    
    # Validate context data
    if [ "$s3_endpoint" == "null" ] || [ -z "$s3_endpoint" ]; then
        echo "Error: s3_endpoint not found in context" >&2
        return 1
    fi
    
    if [ "$s3_region" == "null" ] || [ -z "$s3_region" ]; then
        echo "Error: s3_region not found in context" >&2
        return 1
    fi
    
    if [ "$s3_bucket" == "null" ] || [ -z "$s3_bucket" ]; then
        echo "Error: s3_bucket_name not found in context" >&2
        return 1
    fi
    
    # Export AWS CLI variables
    export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY"
    export AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
    export AWS_DEFAULT_REGION="$s3_region"
    export S3_ENDPOINT="$s3_endpoint"
    export S3_BUCKET="$s3_bucket"
    
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
        --cli-read-timeout 30 \
        --quiet >/dev/null 2>&1; then
        return 1
    fi
    
    if ! aws s3 cp "s3://${S3_BUCKET}/age-keys/ACTIVE-recovery-key.txt" \
        "$temp_dir/recovery.key" \
        --endpoint-url "$S3_ENDPOINT" \
        --cli-connect-timeout 10 \
        --cli-read-timeout 30 \
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
    
    if [ -z "$age_private_key" ] || [ -z "$recovery_private_key" ] || [ -z "$recovery_public_key" ]; then
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
    if ! aws s3 ls "s3://$S3_BUCKET" --endpoint-url "$S3_ENDPOINT" --cli-connect-timeout 10 --cli-read-timeout 30 &>/dev/null; then
        local create_output
        create_output=$(aws s3 mb "s3://$S3_BUCKET" --endpoint-url "$S3_ENDPOINT" --region "$AWS_DEFAULT_REGION" --cli-connect-timeout 10 2>&1)
        local create_exit=$?
        
        if [ $create_exit -ne 0 ]; then
            # Check if bucket now exists (race condition or BucketAlreadyExists)
            if aws s3 ls "s3://$S3_BUCKET" --endpoint-url "$S3_ENDPOINT" --cli-connect-timeout 10 --cli-read-timeout 30 &>/dev/null; then
                # Bucket exists now, continue
                :
            else
                # Real error - display helpful message
                echo "Error: Failed to create S3 bucket '$S3_BUCKET'" >&2
                echo "$create_output" >&2
                echo "" >&2
                echo "S3 bucket naming rules:" >&2
                echo "  - Lowercase letters, numbers, and hyphens only" >&2
                echo "  - Must start and end with alphanumeric character" >&2
                echo "  - Length: 3-63 characters" >&2
                echo "  - Example: my-tenant-bucket" >&2
                return 1
            fi
        fi
    fi
    
    # Upload timestamped backups
    if ! aws s3 cp "$temp_dir/age-key-encrypted.txt" \
        "s3://$S3_BUCKET/age-keys/$timestamp-age-key-encrypted.txt" \
        --endpoint-url "$S3_ENDPOINT" \
        --cli-connect-timeout 10 \
        --cli-read-timeout 30 \
        --quiet 2>&1; then
        echo "Error: Failed to upload encrypted Age key" >&2
        return 1
    fi
    
    if ! aws s3 cp "$temp_dir/recovery-key.txt" \
        "s3://$S3_BUCKET/age-keys/$timestamp-recovery-key.txt" \
        --endpoint-url "$S3_ENDPOINT" \
        --cli-connect-timeout 10 \
        --cli-read-timeout 30 \
        --quiet 2>&1; then
        echo "Error: Failed to upload recovery key" >&2
        return 1
    fi
    
    # Mark as active
    if ! aws s3 cp "$temp_dir/age-key-encrypted.txt" \
        "s3://$S3_BUCKET/age-keys/ACTIVE-age-key-encrypted.txt" \
        --endpoint-url "$S3_ENDPOINT" \
        --cli-connect-timeout 10 \
        --cli-read-timeout 30 \
        --quiet 2>&1; then
        echo "Error: Failed to mark active encrypted key" >&2
        return 1
    fi
    
    if ! aws s3 cp "$temp_dir/recovery-key.txt" \
        "s3://$S3_BUCKET/age-keys/ACTIVE-recovery-key.txt" \
        --endpoint-url "$S3_ENDPOINT" \
        --cli-connect-timeout 10 \
        --cli-read-timeout 30 \
        --quiet 2>&1; then
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
        --cli-connect-timeout 10 \
        --cli-read-timeout 30 &>/dev/null
    return $?
}
