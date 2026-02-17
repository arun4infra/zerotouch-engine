#!/usr/bin/env bash
# Bootstrap Hetzner Object Storage
#
# META_REQUIRE: s3_endpoint (context)
# META_REQUIRE: s3_region (context)
# META_REQUIRE: S3_ACCESS_KEY (env)
# META_REQUIRE: S3_SECRET_KEY (env)

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

echo "Hetzner Object Storage - Bootstrap Provisioning"
echo "================================================"
echo ""

# Read configuration from context
HETZNER_ENDPOINT=$(jq -r '.s3_endpoint' "$ZTC_CONTEXT_FILE")
HETZNER_REGION=$(jq -r '.s3_region' "$ZTC_CONTEXT_FILE")

# Read credentials from environment
HETZNER_S3_ACCESS_KEY="${S3_ACCESS_KEY:?S3_ACCESS_KEY not set}"
HETZNER_S3_SECRET_KEY="${S3_SECRET_KEY:?S3_SECRET_KEY not set}"

# Validate required fields
if [[ -z "$HETZNER_ENDPOINT" || "$HETZNER_ENDPOINT" == "null" ]]; then
    echo "ERROR: s3_endpoint required in context" >&2
    exit 1
fi

if [[ -z "$HETZNER_REGION" || "$HETZNER_REGION" == "null" ]]; then
    echo "ERROR: s3_region required in context" >&2
    exit 1
fi

# Check required tools
if ! command -v aws &> /dev/null; then
    echo "ERROR: AWS CLI not found" >&2
    echo "Install AWS CLI: https://aws.amazon.com/cli/" >&2
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl not found" >&2
    echo "Install kubectl: https://kubernetes.io/docs/tasks/tools/" >&2
    exit 1
fi

echo "✓ Required tools found"
echo ""

echo "✓ Hetzner credentials validated"
echo ""

# Configure AWS CLI for Hetzner Object Storage
export AWS_ACCESS_KEY_ID="$HETZNER_S3_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$HETZNER_S3_SECRET_KEY"

# Function to create bucket with Object Lock
create_bucket_with_lock() {
    local bucket_name=$1
    local retention_days=$2
    
    echo "Creating bucket: $bucket_name"
    
    # Check if bucket already exists
    if aws s3api head-bucket --bucket "$bucket_name" --endpoint-url "$HETZNER_ENDPOINT" 2>/dev/null; then
        echo "⚠️  Bucket $bucket_name already exists"
        return 0
    fi
    
    # Create bucket with Object Lock enabled
    aws s3api create-bucket \
        --bucket "$bucket_name" \
        --endpoint-url "$HETZNER_ENDPOINT" \
        --region "$HETZNER_REGION" \
        --object-lock-enabled-for-bucket \
        --no-cli-pager > /dev/null 2>&1
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create bucket $bucket_name" >&2
        return 1
    fi
    
    echo "✓ Bucket $bucket_name created"
    
    # Configure Object Lock retention (Compliance Mode)
    echo "Configuring Object Lock retention (${retention_days} days)..."
    
    aws s3api put-object-lock-configuration \
        --bucket "$bucket_name" \
        --endpoint-url "$HETZNER_ENDPOINT" \
        --object-lock-configuration "{
            \"ObjectLockEnabled\": \"Enabled\",
            \"Rule\": {
                \"DefaultRetention\": {
                    \"Mode\": \"COMPLIANCE\",
                    \"Days\": $retention_days
                }
            }
        }" \
        --no-cli-pager > /dev/null 2>&1
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to configure Object Lock for $bucket_name" >&2
        return 1
    fi
    
    echo "✓ Object Lock configured (Compliance Mode, ${retention_days} days)"
    echo ""
    
    return 0
}

# Create compliance reports bucket (7-year retention = 2555 days)
create_bucket_with_lock "zerotouch-compliance-reports" 2555

# Create CNPG backups bucket (30-day retention)
create_bucket_with_lock "zerotouch-cnpg-backups" 30

# Verify bucket accessibility
echo "Verifying bucket accessibility..."

for bucket in "zerotouch-compliance-reports" "zerotouch-cnpg-backups"; do
    if aws s3 ls "s3://$bucket" --endpoint-url "$HETZNER_ENDPOINT" > /dev/null 2>&1; then
        echo "✓ Bucket $bucket is accessible"
    else
        echo "ERROR: Failed to access bucket $bucket" >&2
        exit 1
    fi
done

echo ""

# Create Kubernetes secret for Hetzner S3 credentials
echo "Creating Kubernetes secret for Hetzner S3 credentials..."

# Ensure default namespace exists
kubectl create namespace default --dry-run=client -o yaml | kubectl apply -f - > /dev/null 2>&1

kubectl create secret generic hetzner-s3-credentials \
    --namespace=default \
    --from-literal=access-key="$HETZNER_S3_ACCESS_KEY" \
    --from-literal=secret-key="$HETZNER_S3_SECRET_KEY" \
    --from-literal=endpoint="$HETZNER_ENDPOINT" \
    --from-literal=region="$HETZNER_REGION" \
    --dry-run=client -o yaml | kubectl apply -f - > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Secret hetzner-s3-credentials created/updated"
else
    echo "ERROR: Failed to create secret" >&2
    exit 1
fi

echo ""
echo "Summary"
echo "======="
echo ""
echo "✓ Hetzner Object Storage provisioned"
echo ""
echo "Buckets created:"
echo "  - zerotouch-compliance-reports (7-year retention, Compliance Mode)"
echo "  - zerotouch-cnpg-backups (30-day retention, Compliance Mode)"
echo ""
echo "Kubernetes secret:"
echo "  - hetzner-s3-credentials (default namespace)"
echo ""
echo "Hetzner Object Storage Setup"
echo "============================="
echo ""
echo "Endpoint: $HETZNER_ENDPOINT"
echo "Region: $HETZNER_REGION"
echo ""
echo "Verify buckets:"
echo "  aws s3 ls --endpoint-url $HETZNER_ENDPOINT"
echo ""
echo "⚠️  IMPORTANT: Object Lock in Compliance Mode cannot be disabled!"
echo "   Objects are immutable for the retention period."
echo ""

exit 0
