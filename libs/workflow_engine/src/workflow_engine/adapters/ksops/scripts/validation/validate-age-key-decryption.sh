#!/bin/bash
# META_REQUIRE: sops, age, jq
# INCLUDE: shared/s3-helpers.sh

# Validation script: Verify ACTIVE Age keys can decrypt cluster secrets
# Validates that the Age key can decrypt all encrypted secrets

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Validate Age Key Can Decrypt Cluster Secrets              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

FAILED=0

# Read context
if [ -z "$ZTC_CONTEXT_FILE" ]; then
    echo -e "${RED}✗ ZTC_CONTEXT_FILE not set${NC}"
    exit 1
fi

REPO_ROOT=$(jq -r '.repo_root' "$ZTC_CONTEXT_FILE")
SOPS_CONFIG=$(jq -r '.sops_config_path' "$ZTC_CONTEXT_FILE")
SECRETS_DIR=$(jq -r '.secrets_dir' "$ZTC_CONTEXT_FILE")
AGE_PUBLIC_KEY=$(jq -r '.age_public_key' "$ZTC_CONTEXT_FILE")

echo -e "${GREEN}✓ Repository: $REPO_ROOT${NC}"
echo -e "${GREEN}✓ SOPS config: $SOPS_CONFIG${NC}"
echo -e "${GREEN}✓ Secrets directory: $SECRETS_DIR${NC}"
echo ""

# Check required tools
for tool in sops age; do
    if ! command -v $tool &> /dev/null; then
        echo -e "${RED}✗ $tool not found${NC}"
        exit 1
    fi
done

# Get Age private key from environment
if [ -z "$AGE_PRIVATE_KEY" ]; then
    echo -e "${RED}✗ AGE_PRIVATE_KEY environment variable not set${NC}"
    exit 1
fi

# Step 1: Derive public key
echo -e "${BLUE}[1/3] Deriving public key...${NC}"

AGE_PRIVATE_KEY=$(echo "$AGE_PRIVATE_KEY" | xargs)

if ! DERIVED_PUBLIC_KEY=$(echo "$AGE_PRIVATE_KEY" | age-keygen -y 2>&1); then
    echo -e "${RED}✗ Failed to derive public key${NC}"
    FAILED=1
else
    echo -e "${GREEN}✓ Age key validated${NC}"
    echo -e "${GREEN}  Public Key: $DERIVED_PUBLIC_KEY${NC}"
    export SOPS_AGE_KEY="$AGE_PRIVATE_KEY"
fi
echo ""

# Step 2: Verify public key matches .sops.yaml
echo -e "${BLUE}[2/3] Verifying public key matches .sops.yaml...${NC}"

if [ $FAILED -eq 0 ]; then
    if [ ! -f "$SOPS_CONFIG" ]; then
        echo -e "${RED}✗ .sops.yaml not found at $SOPS_CONFIG${NC}"
        FAILED=1
    else
        EXPECTED_PUBLIC_KEY=$(grep "age:" "$SOPS_CONFIG" | sed -E 's/.*age:[[:space:]]*(age1[a-z0-9]+).*/\1/' | head -1)
        if [ -z "$EXPECTED_PUBLIC_KEY" ]; then
            echo -e "${RED}✗ No Age public key found in .sops.yaml${NC}"
            FAILED=1
        elif [ "$DERIVED_PUBLIC_KEY" = "$EXPECTED_PUBLIC_KEY" ]; then
            echo -e "${GREEN}✓ Public key matches .sops.yaml${NC}"
            echo -e "${GREEN}  Expected: $EXPECTED_PUBLIC_KEY${NC}"
            echo -e "${GREEN}  Got:      $DERIVED_PUBLIC_KEY${NC}"
        else
            echo -e "${RED}✗ Public key mismatch${NC}"
            echo -e "${RED}  Expected: $EXPECTED_PUBLIC_KEY${NC}"
            echo -e "${RED}  Got:      $DERIVED_PUBLIC_KEY${NC}"
            FAILED=1
        fi
    fi
fi
echo ""

# Step 3: Test decryption of encrypted secrets
echo -e "${BLUE}[3/3] Testing decryption of encrypted secrets...${NC}"

if [ $FAILED -eq 0 ]; then
    cd "$REPO_ROOT"
    
    SECRET_FILES=$(find "$SECRETS_DIR" -name "*.secret.yaml" 2>/dev/null || echo "")
    
    if [ -z "$SECRET_FILES" ]; then
        echo -e "${YELLOW}⚠ No encrypted secrets found${NC}"
    else
        TOTAL=0
        SUCCESS=0
        MAX_RETRIES=3
        RETRY_DELAY=2
        
        while IFS= read -r secret_file; do
            TOTAL=$((TOTAL + 1))
            SECRET_NAME=$(basename "$secret_file")
            DECRYPTED=0
            
            for attempt in $(seq 1 $MAX_RETRIES); do
                if sops -d "$secret_file" >/dev/null 2>&1; then
                    if [ $attempt -eq 1 ]; then
                        echo -e "${GREEN}  ✓ $SECRET_NAME${NC}"
                    else
                        echo -e "${GREEN}  ✓ $SECRET_NAME (attempt $attempt)${NC}"
                    fi
                    SUCCESS=$((SUCCESS + 1))
                    DECRYPTED=1
                    break
                else
                    if [ $attempt -lt $MAX_RETRIES ]; then
                        echo -e "${YELLOW}  ⏳ $SECRET_NAME (retrying in ${RETRY_DELAY}s...)${NC}"
                        sleep $RETRY_DELAY
                    fi
                fi
            done
            
            if [ $DECRYPTED -eq 0 ]; then
                echo -e "${RED}  ✗ $SECRET_NAME (failed after $MAX_RETRIES attempts)${NC}"
                FAILED=1
            fi
        done <<< "$SECRET_FILES"
        
        echo ""
        if [ $SUCCESS -eq $TOTAL ]; then
            echo -e "${GREEN}✓ All $TOTAL secrets decrypted successfully${NC}"
        else
            echo -e "${RED}✗ Failed to decrypt $((TOTAL - SUCCESS)) of $TOTAL secrets${NC}"
        fi
    fi
fi
echo ""

# Summary
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Validation Summary                                         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ VALIDATION PASSED${NC}"
    echo ""
    echo -e "${YELLOW}Success Criteria Met:${NC}"
    echo -e "  ✓ Age key validated successfully"
    echo -e "  ✓ Public key matches .sops.yaml"
    echo -e "  ✓ All encrypted secrets can be decrypted"
    echo ""
    exit 0
else
    echo -e "${RED}✗ VALIDATION FAILED${NC}"
    echo ""
    exit 1
fi
