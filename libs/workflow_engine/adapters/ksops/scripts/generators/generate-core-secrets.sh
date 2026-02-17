#!/bin/bash
# META_REQUIRE: sops, jq
# INCLUDE: shared/env-helpers.sh

# Generate core platform secrets (non-prefixed variables)
# Creates secrets for org name, tenant repo, and GitHub App credentials

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Processing CORE platform secrets...${NC}"

# Read context
if [ -z "$ZTC_CONTEXT_FILE" ]; then
    echo -e "${RED}✗ ZTC_CONTEXT_FILE not set${NC}"
    exit 1
fi

REPO_ROOT=$(jq -r '.repo_root' "$ZTC_CONTEXT_FILE")
SECRETS_DIR=$(jq -r '.secrets_dir' "$ZTC_CONTEXT_FILE")
SOPS_CONFIG=$(jq -r '.sops_config_path' "$ZTC_CONTEXT_FILE")
ENV_FILE=$(jq -r '.env_file' "$ZTC_CONTEXT_FILE")
TEMPLATE_DIR=$(jq -r '.template_dir' "$ZTC_CONTEXT_FILE")

echo -e "${BLUE}Target directory: ${SECRETS_DIR}${NC}"

mkdir -p "$SECRETS_DIR"

set -a
source "$ENV_FILE"
set +a

CORE_SECRET_FILES=()
CORE_SECRET_COUNT=0

UNIVERSAL_SECRET_TEMPLATE="$TEMPLATE_DIR/universal-secret.yaml"

# Create ORG_NAME and TENANTS_REPO_NAME secrets
if [[ -n "$ORG_NAME" ]]; then
    sed -e "s/SECRET_NAME_PLACEHOLDER/org-name/g" \
        -e "s/NAMESPACE_PLACEHOLDER/kube-system/g" \
        -e "s/ANNOTATIONS_PLACEHOLDER/argocd.argoproj.io\/sync-wave: \"0\"/g" \
        -e "s/SECRET_TYPE_PLACEHOLDER/Opaque/g" \
        -e "s/SECRET_KEY_PLACEHOLDER/value/g" \
        -e "s|SECRET_VALUE_PLACEHOLDER|\"${ORG_NAME}\"|g" \
        "$UNIVERSAL_SECRET_TEMPLATE" > "$SECRETS_DIR/org-name.secret.yaml"
    
    if sops --config "$SOPS_CONFIG" -e -i "$SECRETS_DIR/org-name.secret.yaml" 2>/dev/null; then
        echo -e "${GREEN}  ✓ org-name.secret.yaml${NC}"
        CORE_SECRET_FILES+=("org-name.secret.yaml")
        ((CORE_SECRET_COUNT++))
    fi
fi

if [[ -n "$TENANTS_REPO_NAME" ]]; then
    sed -e "s/SECRET_NAME_PLACEHOLDER/tenants-repo-name/g" \
        -e "s/NAMESPACE_PLACEHOLDER/kube-system/g" \
        -e "s/ANNOTATIONS_PLACEHOLDER/argocd.argoproj.io\/sync-wave: \"0\"/g" \
        -e "s/SECRET_TYPE_PLACEHOLDER/Opaque/g" \
        -e "s/SECRET_KEY_PLACEHOLDER/value/g" \
        -e "s|SECRET_VALUE_PLACEHOLDER|\"${TENANTS_REPO_NAME}\"|g" \
        "$UNIVERSAL_SECRET_TEMPLATE" > "$SECRETS_DIR/tenants-repo-name.secret.yaml"
    
    if sops --config "$SOPS_CONFIG" -e -i "$SECRETS_DIR/tenants-repo-name.secret.yaml" 2>/dev/null; then
        echo -e "${GREEN}  ✓ tenants-repo-name.secret.yaml${NC}"
        CORE_SECRET_FILES+=("tenants-repo-name.secret.yaml")
        ((CORE_SECRET_COUNT++))
    fi
fi

# Process other core secrets from env file
while IFS='=' read -r name value || [ -n "$name" ]; do
    [[ -z "$name" || "$name" =~ ^[[:space:]]*# ]] && continue
    [[ "$name" =~ ^APP_ ]] && continue
    [[ "$name" =~ ^GITHUB_APP_ ]] && continue
    [[ "$name" =~ ^(ORG_NAME|TENANTS_REPO_NAME)$ ]] && continue
    [[ "$name" =~ ^(DEV|STAGING|PROD|PR)_ ]] && continue
    [[ "$value" =~ $'\n' ]] && continue
    [[ "$name" =~ ^GIT_APP_PRIVATE_KEY$ ]] && continue
    [[ "$name" =~ ^AGE_PRIVATE_KEY$ ]] && continue
    [[ ${#value} -gt 500 ]] && continue
    [[ -z "$value" ]] && continue
    
    secret_name=$(echo "$name" | tr '[:upper:]' '[:lower:]' | tr '_' '-')
    secret_key="value"
    secret_namespace="kube-system"
    
    [[ ! "$secret_name" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]] && continue
    
    secret_file="${secret_name}.secret.yaml"
    
    sed -e "s/SECRET_NAME_PLACEHOLDER/${secret_name}/g" \
        -e "s/NAMESPACE_PLACEHOLDER/${secret_namespace}/g" \
        -e "s/ANNOTATIONS_PLACEHOLDER/argocd.argoproj.io\/sync-wave: \"0\"/g" \
        -e "s/SECRET_TYPE_PLACEHOLDER/Opaque/g" \
        -e "s/SECRET_KEY_PLACEHOLDER/${secret_key}/g" \
        -e "s|SECRET_VALUE_PLACEHOLDER|\"${value}\"|g" \
        "$UNIVERSAL_SECRET_TEMPLATE" > "$SECRETS_DIR/$secret_file"
    
    if sops --config "$SOPS_CONFIG" -e -i "$SECRETS_DIR/$secret_file" 2>/dev/null; then
        echo -e "${GREEN}  ✓ ${secret_file}${NC}"
        CORE_SECRET_FILES+=("$secret_file")
        ((CORE_SECRET_COUNT++))
    else
        echo -e "${RED}  ✗ Failed to encrypt: ${secret_file}${NC}"
        rm -f "$SECRETS_DIR/$secret_file"
    fi
done < "$ENV_FILE"

# Create GitHub App credentials secret
if [[ -n "$GIT_APP_ID" && -n "$GIT_APP_INSTALLATION_ID" && -n "$GIT_APP_PRIVATE_KEY" ]]; then
    cat > "$SECRETS_DIR/github-app-credentials.secret.yaml" << EOF
apiVersion: v1
kind: Secret
metadata:
  name: github-app-credentials
  namespace: kube-system
  annotations:
    argocd.argoproj.io/sync-wave: "0"
type: Opaque
stringData:
  git-app-id: "${GIT_APP_ID}"
  git-app-installation-id: "${GIT_APP_INSTALLATION_ID}"
  git-app-private-key: |
EOF
    echo "$GIT_APP_PRIVATE_KEY" | sed 's/^/    /' >> "$SECRETS_DIR/github-app-credentials.secret.yaml"
    
    if sops --config "$SOPS_CONFIG" -e -i "$SECRETS_DIR/github-app-credentials.secret.yaml" 2>/dev/null; then
        echo -e "${GREEN}  ✓ github-app-credentials.secret.yaml${NC}"
        CORE_SECRET_FILES+=("github-app-credentials.secret.yaml")
        ((CORE_SECRET_COUNT++))
    fi
fi

# Add GitHub App secrets to kustomization
for github_secret in github-app-id.secret.yaml github-app-installation-id.secret.yaml github-app-private-key.secret.yaml; do
    if [ -f "$SECRETS_DIR/$github_secret" ]; then
        CORE_SECRET_FILES+=("$github_secret")
        ((CORE_SECRET_COUNT++))
    fi
done

if [ ${#CORE_SECRET_FILES[@]} -gt 0 ]; then
    # Create or append to KSOPS Generator
    if [ ! -f "$SECRETS_DIR/ksops-generator.yaml" ]; then
        cat > "$SECRETS_DIR/ksops-generator.yaml" << EOF
# Generated by KSOPS adapter
apiVersion: viaduct.ai/v1
kind: ksops
metadata:
  name: core-secrets-generator
  annotations:
    config.kubernetes.io/function: |
      exec:
        path: ksops
files:
EOF
    fi
    
    # Append files to generator
    for file in "${CORE_SECRET_FILES[@]}"; do
        if ! grep -q "\./$file" "$SECRETS_DIR/ksops-generator.yaml" 2>/dev/null; then
            echo "  - ./$file" >> "$SECRETS_DIR/ksops-generator.yaml"
        fi
    done
    
    # Create Kustomization if it doesn't exist
    if [ ! -f "$SECRETS_DIR/kustomization.yaml" ]; then
        cat > "$SECRETS_DIR/kustomization.yaml" << EOF
# Generated by KSOPS adapter
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

generators:
- ksops-generator.yaml
EOF
    fi
    echo -e "${GREEN}  ✓ kustomization.yaml (KSOPS generator with ${CORE_SECRET_COUNT} secrets)${NC}"
else
    echo -e "${YELLOW}  ⚠️  No core platform secrets found${NC}"
fi
echo ""
