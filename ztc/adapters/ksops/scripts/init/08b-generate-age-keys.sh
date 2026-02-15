#!/usr/bin/env bash
# Generate Age keypair for SOPS encryption
# Reads context from $ZTC_CONTEXT_FILE and secrets from environment variables
# Checks S3 first for existing Age key, generates new if not found

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HELPERS_DIR="$SCRIPT_DIR/../helpers"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Age Keypair Generation for SOPS Encryption                ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Source helper libraries
if [ ! -f "$HELPERS_DIR/s3-helpers.sh" ]; then
    echo -e "${RED}✗ Error: s3-helpers.sh not found${NC}"
    exit 1
fi

if [ ! -f "$HELPERS_DIR/age-helpers.sh" ]; then
    echo -e "${RED}✗ Error: age-helpers.sh not found${NC}"
    exit 1
fi

source "$HELPERS_DIR/s3-helpers.sh"
source "$HELPERS_DIR/age-helpers.sh"

# Configure S3 credentials
echo -e "${BLUE}Configuring S3 credentials...${NC}"
if ! configure_s3_credentials; then
    echo -e "${RED}✗ Error: Failed to configure S3 credentials${NC}"
    exit 1
fi
echo -e "${GREEN}✓ S3 credentials configured${NC}"
echo ""

# Check if Age key exists in S3
echo -e "${BLUE}Checking S3 for existing Age key...${NC}"
if s3_age_key_exists; then
    echo -e "${YELLOW}⚠ Existing Age key found in S3${NC}"
    echo -e "${BLUE}Retrieving existing Age key to maintain secret decryption...${NC}"
    
    # Retrieve Age key from S3
    if ! AGE_PRIVATE_KEY=$(s3_retrieve_age_key); then
        echo -e "${RED}✗ Error: Failed to retrieve Age key from S3${NC}"
        exit 1
    fi
    
    # Validate and clean private key
    if ! AGE_PRIVATE_KEY=$(validate_age_private_key "$AGE_PRIVATE_KEY"); then
        echo -e "${RED}✗ Error: Invalid Age private key format from S3${NC}"
        exit 1
    fi
    
    # Derive public key from private key
    if ! AGE_PUBLIC_KEY=$(derive_age_public_key "$AGE_PRIVATE_KEY"); then
        echo -e "${RED}✗ Error: Failed to derive public key from existing private key${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Existing Age key retrieved from S3${NC}"
    echo ""
else
    echo -e "${BLUE}No existing Age key in S3, generating new keypair...${NC}"

    # Generate new Age keypair
    if ! generate_age_keypair; then
        echo -e "${RED}✗ Error: Failed to generate Age keypair${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ Age keypair generated successfully${NC}"
    echo ""
fi

# Export keys to environment variables (already done by helper functions)
export AGE_PUBLIC_KEY
export AGE_PRIVATE_KEY

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Generated Keys                                             ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Public Key:${NC}"
echo -e "  $AGE_PUBLIC_KEY"
echo ""
echo -e "${GREEN}Private Key:${NC}"
echo -e "  $AGE_PRIVATE_KEY"
echo ""

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Environment Variables                                      ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✓ AGE_PUBLIC_KEY exported${NC}"
echo -e "${GREEN}✓ AGE_PRIVATE_KEY exported${NC}"
echo ""

# Note: No exit statement - this script is meant to be sourced to preserve environment variables
