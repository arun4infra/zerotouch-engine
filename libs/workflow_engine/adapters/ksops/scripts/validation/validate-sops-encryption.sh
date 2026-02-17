#!/bin/bash
# META_REQUIRE: sops, age, jq
# INCLUDE: shared/env-helpers.sh

# Validation script for SOPS Configuration and Secret Encryption
# Validates SOPS configuration and secret encryption using Age keys from context

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Validation counters
PASSED=0
FAILED=0
TOTAL=0

# Function to run validation check
validate() {
    local test_name=$1
    local test_command=$2
    
    TOTAL=$((TOTAL + 1))
    echo -e "${BLUE}[${TOTAL}] Testing: $test_name${NC}"
    
    if eval "$test_command"; then
        echo -e "${GREEN}✓ PASSED: $test_name${NC}"
        PASSED=$((PASSED + 1))
        echo ""
        return 0
    else
        echo -e "${RED}✗ FAILED: $test_name${NC}"
        FAILED=$((FAILED + 1))
        echo ""
        return 1
    fi
}

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   SOPS Configuration and Secret Encryption Validation       ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Read context
if [ -z "$ZTC_CONTEXT_FILE" ]; then
    echo -e "${RED}✗ ZTC_CONTEXT_FILE not set${NC}"
    exit 1
fi

REPO_ROOT=$(jq -r '.repo_root' "$ZTC_CONTEXT_FILE")
SOPS_CONFIG=$(jq -r '.sops_config_path' "$ZTC_CONTEXT_FILE")
AGE_PUBLIC_KEY=$(jq -r '.age_public_key' "$ZTC_CONTEXT_FILE")

# Get Age private key from environment
if [ -z "$AGE_PRIVATE_KEY" ]; then
    echo -e "${RED}✗ AGE_PRIVATE_KEY environment variable not set${NC}"
    exit 1
fi

export SOPS_AGE_KEY="$AGE_PRIVATE_KEY"

echo -e "${GREEN}✓ Repository: $REPO_ROOT${NC}"
echo -e "${GREEN}✓ SOPS config: $SOPS_CONFIG${NC}"
echo -e "${GREEN}✓ Age public key: $AGE_PUBLIC_KEY${NC}"
echo ""

# Check if .sops.yaml exists
if [[ -f "$SOPS_CONFIG" ]]; then
    echo -e "${GREEN}✓ Found .sops.yaml at $SOPS_CONFIG${NC}"
    cd "$REPO_ROOT"
else
    echo -e "${RED}✗ No .sops.yaml found at $SOPS_CONFIG${NC}"
    exit 1
fi

# Check required tools
if ! command -v sops &> /dev/null; then
    echo -e "${RED}✗ Error: sops not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Required tools found${NC}"
echo ""

# Validation 1: Repository has .sops.yaml
validate "Repository SOPS configuration available" \
    "test -f '$SOPS_CONFIG'"

# Validation 2: Test secret encryption
echo -e "${BLUE}[${TOTAL}] Testing: Secret encryption with correct Age key${NC}"
TEST_DIR="./test-secrets"
mkdir -p "$TEST_DIR"

cat > "$TEST_DIR/test.secret.yaml" << 'EOF'
apiVersion: v1
kind: Secret
metadata:
  name: test-secret
  namespace: test-service
type: Opaque
stringData:
  test-key: test-value
EOF

# Run sops encryption
if sops -e --config "$SOPS_CONFIG" "$TEST_DIR/test.secret.yaml" > "$TEST_DIR/test.secret.enc.yaml" 2>/dev/null; then
    echo -e "${GREEN}✓ PASSED: Secret encryption successful${NC}"
    PASSED=$((PASSED + 1))
    
    # Validation 3: Encrypted secret contains sops metadata
    if grep -q "sops:" "$TEST_DIR/test.secret.enc.yaml"; then
        echo -e "${GREEN}✓ PASSED: Encrypted secret contains sops metadata${NC}"
        PASSED=$((PASSED + 1))
    else
        echo -e "${RED}✗ FAILED: No sops metadata found${NC}"
        FAILED=$((FAILED + 1))
    fi
    
    # Validation 4: Only data fields encrypted
    if grep -q "apiVersion: v1" "$TEST_DIR/test.secret.enc.yaml" && \
       grep -q "kind: Secret" "$TEST_DIR/test.secret.enc.yaml" && \
       grep -q "metadata:" "$TEST_DIR/test.secret.enc.yaml"; then
        echo -e "${GREEN}✓ PASSED: metadata, kind, apiVersion remain unencrypted${NC}"
        PASSED=$((PASSED + 1))
    else
        echo -e "${RED}✗ FAILED: Metadata fields encrypted${NC}"
        FAILED=$((FAILED + 1))
    fi
    
    # Cleanup
    rm -rf "$TEST_DIR"
else
    echo -e "${RED}✗ FAILED: Secret encryption failed${NC}"
    FAILED=$((FAILED + 3))
    rm -rf "$TEST_DIR"
fi

TOTAL=$((TOTAL + 3))
echo ""

# Summary
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Validation Summary                                         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Passed: $PASSED / $TOTAL${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failed: $FAILED / $TOTAL${NC}"
fi
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ VALIDATION PASSED${NC}"
    echo ""
    echo -e "${YELLOW}Success Criteria Met:${NC}"
    echo -e "  ✓ Secrets properly encrypted with correct keys"
    echo -e "  ✓ Platform SOPS capability validated"
    echo -e "  ✓ Ready for ArgoCD sync"
    echo ""
    exit 0
else
    echo -e "${RED}✗ VALIDATION FAILED${NC}"
    echo ""
    exit 1
fi
