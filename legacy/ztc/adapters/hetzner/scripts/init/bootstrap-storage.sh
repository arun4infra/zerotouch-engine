#!/bin/bash
# Bootstrap Hetzner Object Storage
# Reads context from $ZTC_CONTEXT_FILE and secrets from environment variables
# Creates S3 buckets with Object Lock for compliance and backups

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Hetzner Storage Bootstrap ===${NC}"
echo ""

# Validate context file
if [ -z "$ZTC_CONTEXT_FILE" ] || [ ! -f "$ZTC_CONTEXT_FILE" ]; then
    echo -e "${RED}✗ Error: ZTC_CONTEXT_FILE not set or file not found${NC}"
    exit 1
fi

# Check for jq
if ! command -v jq &> /dev/null; then
    echo -e "${RED}✗ Error: jq not found (required for JSON parsing)${NC}"
    exit 1
fi

# Read context data
S3_ENDPOINT=$(jq -r '.s3_endpoint' "$ZTC_CONTEXT_FILE")
S3_REGION=$(jq -r '.s3_region' "$ZTC_CONTEXT_FILE")

# Validate context data
if [ "$S3_ENDPOINT" == "null" ] || [ -z "$S3_ENDPOINT" ]; then
    echo -e "${RED}✗ Error: s3_endpoint not found in context${NC}"
    exit 1
fi

if [ "$S3_REGION" == "null" ] || [ -z "$S3_REGION" ]; then
    echo -e "${RED}✗ Error: s3_region not found in context${NC}"
    exit 1
fi

# Validate secret environment variables
if [ -z "$HETZNER_S3_ACCESS_KEY" ]; then
    echo -e "${RED}✗ Error: HETZNER_S3_ACCESS_KEY environment variable not set${NC}"
    exit 1
fi

if [ -z "$HETZNER_S3_SECRET_KEY" ]; then
    echo -e "${RED}✗ Error: HETZNER_S3_SECRET_KEY environment variable not set${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Context and secrets validated${NC}"
echo ""

# Export environment variables
export HETZNER_S3_ENDPOINT="$S3_ENDPOINT"
export HETZNER_S3_REGION="$S3_REGION"
export HETZNER_S3_ACCESS_KEY="$HETZNER_S3_ACCESS_KEY"
export HETZNER_S3_SECRET_KEY="$HETZNER_S3_SECRET_KEY"

# Check required tools
if ! command -v aws &> /dev/null; then
    echo -e "${RED}✗ Error: AWS CLI not found${NC}"
    echo -e "Install AWS CLI: https://aws.amazon.com/cli/"
    exit 1
fi

echo -e "${GREEN}✓ AWS CLI found${NC}"
echo ""

# Configure AWS CLI for Hetzner Object Storage
export AWS_ACCESS_KEY_ID="$HETZNER_S3_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$HETZNER_S3_SECRET_KEY"

# Function to create bucket with Object Lock
create_bucket_with_lock() {
    local bucket_name=$1
    local retention_days=$2
    
    echo -e "${BLUE}Creating bucket: $bucket_name${NC}"
    
    # Check if bucket already exists
    if aws s3api head-bucket --bucket "$bucket_name" --endpoint-url "$HETZNER_S3_ENDPOINT" 2>/dev/null; then
        echo -e "${GREEN}✓ Bucket $bucket_name already exists${NC}"
        return 0
    fi
    
    # Create bucket with Object Lock enabled
    aws s3api create-bucket \
        --bucket "$bucket_name" \
        --endpoint-url "$HETZNER_S3_ENDPOINT" \
        --region "$HETZNER_S3_REGION" \
        --object-lock-enabled-for-bucket \
        --no-cli-pager > /dev/null 2>&1
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ Failed to create bucket $bucket_name${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓ Bucket $bucket_name created${NC}"
    
    # Configure Object Lock retention (Compliance Mode)
    aws s3api put-object-lock-configuration \
        --bucket "$bucket_name" \
        --endpoint-url "$HETZNER_S3_ENDPOINT" \
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
        echo -e "${RED}✗ Failed to configure Object Lock for $bucket_name${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓ Object Lock configured (${retention_days} days)${NC}"
    echo ""
}

# Create buckets
create_bucket_with_lock "zerotouch-compliance-reports" 2555
create_bucket_with_lock "zerotouch-cnpg-backups" 30

# Verify bucket accessibility
echo -e "${BLUE}Verifying bucket accessibility...${NC}"

for bucket in "zerotouch-compliance-reports" "zerotouch-cnpg-backups"; do
    if aws s3 ls "s3://$bucket" --endpoint-url "$HETZNER_S3_ENDPOINT" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Bucket $bucket is accessible${NC}"
    else
        echo -e "${RED}✗ Failed to access bucket $bucket${NC}"
        exit 1
    fi
done

echo ""
echo -e "${GREEN}✓ Hetzner Object Storage bootstrap complete${NC}"
echo ""

exit 0
