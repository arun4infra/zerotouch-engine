#!/bin/bash
# META_REQUIRE: sops, jq
# INCLUDE: shared/env-helpers.sh

# Generate SOPS-encrypted *.secret.yaml from environment variables
# Processes environment-prefixed secrets and creates encrypted YAML files

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Generate SOPS-Encrypted Secrets                           ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Read context
if [ -z "$ZTC_CONTEXT_FILE" ]; then
    echo -e "${RED}✗ ZTC_CONTEXT_FILE not set${NC}"
    exit 1
fi

REPO_ROOT=$(jq -r '.repo_root' "$ZTC_CONTEXT_FILE")
SECRETS_DIR=$(jq -r '.secrets_dir' "$ZTC_CONTEXT_FILE")
SOPS_CONFIG=$(jq -r '.sops_config_path' "$ZTC_CONTEXT_FILE")
ENV_PREFIX=$(jq -r '.env_prefix' "$ZTC_CONTEXT_FILE")
TENANT_NAME=$(jq -r '.tenant_name // empty' "$ZTC_CONTEXT_FILE")
ENV_FILE=$(jq -r '.env_file' "$ZTC_CONTEXT_FILE")
TEMPLATE_DIR=$(jq -r '.template_dir' "$ZTC_CONTEXT_FILE")

if [ -n "$TENANT_NAME" ]; then
    echo -e "${GREEN}✓ Tenant: $TENANT_NAME${NC}"
fi
echo -e "${GREEN}✓ Environment prefix: $ENV_PREFIX${NC}"
echo -e "${GREEN}✓ Repository: $REPO_ROOT${NC}"
echo -e "${GREEN}✓ Output directory: $SECRETS_DIR${NC}"

# Check if env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}✗ Error: $ENV_FILE not found${NC}"
    exit 1
fi

# Check if sops is installed
if ! command -v sops &> /dev/null; then
    echo -e "${RED}✗ Error: sops not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Using SOPS config: $SOPS_CONFIG${NC}"
echo -e "${GREEN}✓ Reading from: $ENV_FILE${NC}"
echo ""

# Create secrets directory
mkdir -p "$SECRETS_DIR"

echo -e "${BLUE}Processing ${ENV_PREFIX}_ prefixed secrets...${NC}"

# Read and process secrets
SECRET_COUNT=0

# Source .env file to preserve multiline values
set -a
source "$ENV_FILE"
set +a

# Get all variable names from .env that match prefix
ENV_VARS=$(grep -E "^${ENV_PREFIX}_" "$ENV_FILE" | grep -v '^[[:space:]]*#' | cut -d'=' -f1)

for name in $ENV_VARS; do
    # Get value from sourced environment
    value="${!name}"
    
    # Skip if empty
    [[ -z "$value" ]] && continue
    
    # Extract secret name (remove prefix)
    if [[ "$name" =~ ^${ENV_PREFIX}_(.+)$ ]]; then
        secret_name=$(echo "${BASH_REMATCH[1]}" | tr '[:upper:]' '[:lower:]' | tr '_' '-')
        secret_key="${BASH_REMATCH[1]}"
    else
        continue
    fi
    
    SECRET_FILE="$SECRETS_DIR/${secret_name}.secret.yaml"
    
    # Determine namespace from tenant's namespace file
    secret_namespace="default"
    if [ -n "$TENANT_NAME" ]; then
        TENANT_DIR="$(dirname "$(dirname "$(dirname "$SECRETS_DIR")")")"
        NAMESPACE_FILE="$TENANT_DIR/00-namespace.yaml"
        if [ -f "$NAMESPACE_FILE" ]; then
            secret_namespace=$(grep -A1 "^metadata:" "$NAMESPACE_FILE" | grep "name:" | awk '{print $2}')
        fi
    fi
    
    # Check if value is multiline
    if [[ "$value" == *$'\n'* ]]; then
        # Multiline value: use data field with base64 encoding
        TEMPLATE_FILE="$TEMPLATE_DIR/universal-secret-data.yaml"
        if [ ! -f "$TEMPLATE_FILE" ]; then
            echo -e "${RED}✗ Error: Template not found: $TEMPLATE_FILE${NC}"
            exit 1
        fi
        
        value_base64=$(echo -n "$value" | base64)
        
        sed -e "s/SECRET_NAME_PLACEHOLDER/${secret_name}/g" \
            -e "s/NAMESPACE_PLACEHOLDER/${secret_namespace}/g" \
            -e "s/ANNOTATIONS_PLACEHOLDER/argocd.argoproj.io\/sync-wave: \"0\"/g" \
            -e "s/SECRET_TYPE_PLACEHOLDER/Opaque/g" \
            -e "s/SECRET_KEY_PLACEHOLDER/${secret_key}/g" \
            -e "s|SECRET_VALUE_BASE64_PLACEHOLDER|${value_base64}|g" \
            "$TEMPLATE_FILE" > "$SECRET_FILE"
    else
        # Single-line value: use stringData field
        TEMPLATE_FILE="$TEMPLATE_DIR/universal-secret.yaml"
        if [ ! -f "$TEMPLATE_FILE" ]; then
            echo -e "${RED}✗ Error: Template not found: $TEMPLATE_FILE${NC}"
            exit 1
        fi
        
        sed -e "s/SECRET_NAME_PLACEHOLDER/${secret_name}/g" \
            -e "s/NAMESPACE_PLACEHOLDER/${secret_namespace}/g" \
            -e "s/ANNOTATIONS_PLACEHOLDER/argocd.argoproj.io\/sync-wave: \"0\"/g" \
            -e "s/SECRET_TYPE_PLACEHOLDER/Opaque/g" \
            -e "s/SECRET_KEY_PLACEHOLDER/${secret_key}/g" \
            -e "s|SECRET_VALUE_PLACEHOLDER|\"${value}\"|g" \
            "$TEMPLATE_FILE" > "$SECRET_FILE"
    fi
    
    # Encrypt with SOPS
    SOPS_CMD="sops -e -i"
    if [ -n "$SOPS_CONFIG" ] && [ -f "$SOPS_CONFIG" ]; then
        SOPS_CMD="sops --config $SOPS_CONFIG -e -i"
    fi
    
    if $SOPS_CMD "$SECRET_FILE" 2>/dev/null; then
        echo -e "${GREEN}✓ Created: ${secret_name}.secret.yaml${NC}"
        ((SECRET_COUNT++))
    else
        echo -e "${RED}✗ Failed to encrypt: ${secret_name}.secret.yaml${NC}"
        rm -f "$SECRET_FILE"
    fi
done

if [ $SECRET_COUNT -eq 0 ]; then
    echo -e "${YELLOW}⚠️  No secrets found with ${ENV_PREFIX}_ prefix${NC}"
    exit 0
fi

echo ""
echo -e "${GREEN}✓ Created $SECRET_COUNT encrypted secret files${NC}"

# Generate ksops-generator.yaml and kustomization.yaml
GENERATOR_FILE="$SECRETS_DIR/ksops-generator.yaml"
KUSTOMIZATION_FILE="$SECRETS_DIR/kustomization.yaml"

echo ""
echo -e "${BLUE}Generating KSOPS configuration files...${NC}"

# Copy template for ksops-generator.yaml
if [ ! -f "$TEMPLATE_DIR/ksops-generator.yaml" ]; then
    echo -e "${RED}✗ Error: Template not found: $TEMPLATE_DIR/ksops-generator.yaml${NC}"
    exit 1
fi
cp "$TEMPLATE_DIR/ksops-generator.yaml" "$GENERATOR_FILE"

# Add all secret files to the generator
for secret_file in "$SECRETS_DIR"/*.secret.yaml; do
    if [ -f "$secret_file" ]; then
        basename_file=$(basename "$secret_file")
        echo "  - ./$basename_file" >> "$GENERATOR_FILE"
    fi
done

echo -e "${GREEN}✓ Created: ksops-generator.yaml${NC}"

# Copy template for kustomization.yaml
if [ ! -f "$TEMPLATE_DIR/kustomization.yaml" ]; then
    echo -e "${RED}✗ Error: Template not found: $TEMPLATE_DIR/kustomization.yaml${NC}"
    exit 1
fi
cp "$TEMPLATE_DIR/kustomization.yaml" "$KUSTOMIZATION_FILE"

echo -e "${GREEN}✓ Created: kustomization.yaml${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
if [ -n "$TENANT_NAME" ]; then
    echo -e "  1. Review: ${GREEN}ls -la $SECRETS_DIR${NC}"
    echo -e "  2. Commit secrets to repository"
else
    echo -e "  1. Review: ${GREEN}ls -la $SECRETS_DIR${NC}"
    echo -e "  2. Commit secrets to repository"
fi
echo ""
echo -e "${GREEN}✅ Encryption complete${NC}"

exit 0
