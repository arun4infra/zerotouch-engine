#!/bin/bash
# META_REQUIRE: sops, age, jq, yq
# INCLUDE: shared/s3-helpers.sh
# INCLUDE: shared/env-helpers.sh

# Create .env file from encrypted secrets in Git
# Retrieves Age key and decrypts all secrets to generate .env file

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Create .env from Encrypted Secrets                        ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Read context
if [ -z "$ZTC_CONTEXT_FILE" ]; then
    echo -e "${RED}✗ ZTC_CONTEXT_FILE not set${NC}"
    exit 1
fi

REPO_ROOT=$(jq -r '.repo_root' "$ZTC_CONTEXT_FILE")
ENV_PREFIX=$(jq -r '.env_prefix' "$ZTC_CONTEXT_FILE")
SECRETS_DIR=$(jq -r '.secrets_dir' "$ZTC_CONTEXT_FILE")
SOPS_CONFIG=$(jq -r '.sops_config_path' "$ZTC_CONTEXT_FILE")
ENV_FILE=$(jq -r '.env_file' "$ZTC_CONTEXT_FILE")

echo -e "${GREEN}✓ Environment prefix: $ENV_PREFIX${NC}"
echo -e "${GREEN}✓ Repository: $REPO_ROOT${NC}"
echo ""

# Check required tools
for tool in age sops; do
    if ! command -v $tool &> /dev/null; then
        echo -e "${RED}✗ Error: $tool not found${NC}"
        exit 1
    fi
done
echo -e "${GREEN}✓ Required tools installed${NC}"
echo ""

# Get Age key from environment
echo -e "${BLUE}[1/4] Retrieving Age key...${NC}"

if [ -z "$AGE_PRIVATE_KEY" ]; then
    echo -e "${RED}✗ AGE_PRIVATE_KEY environment variable not set${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Age key loaded from environment${NC}"
echo ""

# Derive public key
echo -e "${BLUE}[2/4] Deriving public key...${NC}"

AGE_PRIVATE_KEY=$(echo "$AGE_PRIVATE_KEY" | xargs)

if ! AGE_PUBLIC_KEY=$(echo "$AGE_PRIVATE_KEY" | age-keygen -y 2>&1); then
    echo -e "${RED}✗ Failed to derive public key${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Age key validated${NC}"
echo ""

# Validate against .sops.yaml
echo -e "${BLUE}[3/4] Validating Age key...${NC}"

if [ ! -f "$SOPS_CONFIG" ]; then
    echo -e "${RED}✗ .sops.yaml not found at $SOPS_CONFIG${NC}"
    exit 1
fi

EXPECTED_PUBLIC_KEY=$(grep "age:" "$SOPS_CONFIG" | sed -E 's/.*age:[[:space:]]*(age1[a-z0-9]+).*/\1/' | head -1)

if [ "$AGE_PUBLIC_KEY" != "$EXPECTED_PUBLIC_KEY" ]; then
    echo -e "${RED}✗ Age key mismatch${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Age key matches .sops.yaml${NC}"
echo ""

# Decrypt secrets and generate .env
echo -e "${BLUE}[4/4] Decrypting secrets and generating .env...${NC}"

if [ ! -d "$SECRETS_DIR" ]; then
    echo -e "${RED}✗ Secrets directory not found: $SECRETS_DIR${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Secrets directory found: $SECRETS_DIR${NC}"

export SOPS_AGE_KEY="$AGE_PRIVATE_KEY"
echo -e "${GREEN}✓ SOPS_AGE_KEY configured for decryption${NC}"

echo -e "${BLUE}Creating .env file: $ENV_FILE${NC}"
if ! > "$ENV_FILE" 2>&1; then
    echo -e "${RED}✗ Failed to create .env file${NC}"
    exit 1
fi
echo -e "${GREEN}✓ .env file created${NC}"

SECRET_COUNT=0

# Process secrets from directory
echo -e "${BLUE}Processing secrets from: $SECRETS_DIR${NC}"
echo -e "${BLUE}Prefix: $ENV_PREFIX${NC}"

while IFS= read -r secret_file; do
    basename_file=$(basename "$secret_file")
    
    # Skip core secrets (processed separately without prefix)
    if [[ "$basename_file" =~ ^(org-name|tenants-repo-name|github-app-credentials|git-app-.*)\.secret\.yaml$ ]]; then
        continue
    fi
    
    # Skip ArgoCD-only secrets
    if [[ "$basename_file" =~ ^(repo-zerotouch-tenants|ghcr-pull-secret)\.secret\.yaml$ ]]; then
        continue
    fi
    
    # Decrypt secret
    set +e
    decrypted=$(sops -d "$secret_file" 2>&1)
    exit_code=$?
    set -e
    
    if [ $exit_code -ne 0 ]; then
        echo -e "${RED}✗ Failed to decrypt: $(basename "$secret_file")${NC}"
        exit 1
    fi
    
    # Extract secret name
    secret_name=$(echo "$decrypted" | grep "name:" | head -1 | sed 's/.*name: *//')
    
    # Extract all stringData keys and values
    in_string_data=false
    while IFS= read -r line; do
        if [[ "$line" =~ ^stringData: ]]; then
            in_string_data=true
            continue
        fi
        
        if [[ "$in_string_data" == true ]]; then
            if [[ "$line" =~ ^[a-zA-Z] ]]; then
                break
            fi
            
            if [[ "$line" =~ ^[[:space:]]+([^:]+):[[:space:]]*(.+)$ ]]; then
                key="${BASH_REMATCH[1]}"
                value="${BASH_REMATCH[2]}"
                
                value="${value#\"}"
                value="${value%\"}"
                
                env_var_name=$(echo "$secret_name" | tr '[:lower:]' '[:upper:]' | tr '-' '_')
                
                if [ "$key" != "value" ]; then
                    key_upper=$(echo "$key" | tr '[:lower:]' '[:upper:]' | tr '-' '_')
                    env_var_name="${env_var_name}_${key_upper}"
                fi
                
                printf '%s=%s\n' "${ENV_PREFIX}${env_var_name}" "$value" >> "$ENV_FILE"
                ((++SECRET_COUNT))
            fi
        fi
    done <<< "$decrypted"
done < <(find "$SECRETS_DIR" -name "*.secret.yaml" -type f)

# Process core secrets (no prefix)
while IFS= read -r secret_file; do
    basename_file=$(basename "$secret_file")
    
    secret_name_check=$(sops -d "$secret_file" 2>/dev/null | grep "name:" | head -1 | sed 's/.*name: *//' || echo "")
    
    if [[ ! "$secret_name_check" =~ ^(org-name|tenants-repo-name|github-app-credentials|git-app-.*)$ ]]; then
        continue
    fi
    
    if [[ "$basename_file" =~ ^(git-app-id|git-app-installation-id)\.secret\.yaml$ ]]; then
        if [ -f "$SECRETS_DIR/github-app-credentials.secret.yaml" ]; then
            continue
        fi
    fi
    
    if [[ "$basename_file" == "age-private-key.secret.yaml" ]]; then
        continue
    fi
    
    set +e
    decrypted=$(sops -d "$secret_file" 2>&1)
    exit_code=$?
    set -e
    
    if [ $exit_code -ne 0 ]; then
        echo -e "${RED}✗ Failed to decrypt: $(basename "$secret_file")${NC}"
        exit 1
    fi
    
    secret_name=$(echo "$decrypted" | grep "name:" | head -1 | sed 's/.*name: *//')
    
    if command -v yq &> /dev/null; then
        keys=$(echo "$decrypted" | yq eval '.stringData | keys | .[]' - 2>/dev/null)
        
        while IFS= read -r key; do
            [ -z "$key" ] && continue
            
            value=$(echo "$decrypted" | yq eval ".stringData.\"$key\"" - 2>/dev/null)
            
            if [ "$secret_name" = "github-app-credentials" ]; then
                env_var_name=$(echo "$key" | tr '[:lower:]' '[:upper:]' | tr '-' '_')
            else
                env_var_name=$(echo "$secret_name" | tr '[:lower:]' '[:upper:]' | tr '-' '_')
                if [ "$key" != "value" ]; then
                    key_upper=$(echo "$key" | tr '[:lower:]' '[:upper:]' | tr '-' '_')
                    env_var_name="${env_var_name}_${key_upper}"
                fi
            fi
            
            write_env_var "$env_var_name" "$value" "$ENV_FILE"
            ((++SECRET_COUNT))
        done <<< "$keys"
    fi
done < <(find "$SECRETS_DIR" -name "*.secret.yaml" -type f)

if [ $SECRET_COUNT -eq 0 ]; then
    echo -e "${RED}✗ No secrets decrypted${NC}"
    exit 1
fi

# Add AGE_PRIVATE_KEY to .env if not already there
if ! grep -q "^AGE_PRIVATE_KEY=" "$ENV_FILE" 2>/dev/null; then
    if [ -n "${AGE_PRIVATE_KEY:-}" ]; then
        echo "AGE_PRIVATE_KEY=$AGE_PRIVATE_KEY" >> "$ENV_FILE"
        echo -e "${GREEN}✓ Added AGE_PRIVATE_KEY to .env${NC}"
    fi
fi

echo -e "${GREEN}✓ Decrypted $SECRET_COUNT secret values${NC}"
echo -e "${GREEN}✓ Generated: $ENV_FILE${NC}"
echo ""

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Summary                                                    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✓ Age key validated${NC}"
echo -e "${GREEN}✓ $SECRET_COUNT secrets decrypted${NC}"
echo -e "${GREEN}✓ .env file created with ${ENV_PREFIX}* prefixed variables${NC}"
echo ""

exit 0
