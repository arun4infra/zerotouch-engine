#!/usr/bin/env bash
# Create encrypted backup of Age private key
#
# META_REQUIRE: None
#
# This script generates a recovery master key, encrypts the Age private key,
# and stores both in Kubernetes secrets for automated recovery.

set -euo pipefail

# Validate context file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

echo "Age Key Backup - Automated Recovery Setup"
echo "=========================================="
echo ""

# Check required tools
if ! command -v age-keygen &> /dev/null; then
    echo "ERROR: age-keygen not found" >&2
    echo "Install age: https://github.com/FiloSottile/age" >&2
    exit 1
fi

if ! command -v age &> /dev/null; then
    echo "ERROR: age not found" >&2
    echo "Install age: https://github.com/FiloSottile/age" >&2
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl not found" >&2
    echo "Install kubectl: https://kubernetes.io/docs/tasks/tools/" >&2
    exit 1
fi

echo "✓ Required tools found"
echo ""

# Check if AGE_PRIVATE_KEY environment variable is set
if [ -z "${AGE_PRIVATE_KEY:-}" ]; then
    echo "ERROR: AGE_PRIVATE_KEY environment variable not set" >&2
    echo "Run generate-age-keys.sh first" >&2
    exit 1
fi

echo "✓ Age private key found in environment"
echo ""

# Generate recovery master key
echo "Generating recovery master key..."
RECOVERY_KEYGEN_OUTPUT=$(age-keygen 2>&1)

RECOVERY_PUBLIC_KEY=$(echo "$RECOVERY_KEYGEN_OUTPUT" | grep "# public key:" | sed 's/# public key: //')
RECOVERY_PRIVATE_KEY=$(echo "$RECOVERY_KEYGEN_OUTPUT" | grep "^AGE-SECRET-KEY-1" | head -n 1)

if [ -z "$RECOVERY_PUBLIC_KEY" ] || [ -z "$RECOVERY_PRIVATE_KEY" ]; then
    echo "ERROR: Failed to generate recovery master key" >&2
    exit 1
fi

echo "✓ Recovery master key generated"
echo ""

# Encrypt Age private key with recovery master key
echo "Encrypting Age private key..."

ENCRYPTED_AGE_KEY=$(echo "$AGE_PRIVATE_KEY" | age -r "$RECOVERY_PUBLIC_KEY" -a)

if [ -z "$ENCRYPTED_AGE_KEY" ]; then
    echo "ERROR: Failed to encrypt Age private key" >&2
    exit 1
fi

echo "✓ Age private key encrypted"
echo ""

# Ensure ArgoCD namespace exists
if ! kubectl get namespace argocd &> /dev/null; then
    echo "ERROR: ArgoCD namespace not found" >&2
    echo "Run inject-age-key.sh first to create the namespace" >&2
    exit 1
fi

# Create age-backup-encrypted secret
echo "Creating age-backup-encrypted secret..."

kubectl create secret generic age-backup-encrypted \
    --namespace=argocd \
    --from-literal=encrypted-key.txt="$ENCRYPTED_AGE_KEY" \
    --dry-run=client -o yaml | kubectl apply -f - > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Secret age-backup-encrypted created/updated"
else
    echo "ERROR: Failed to create age-backup-encrypted secret" >&2
    exit 1
fi

# Create recovery-master-key secret
echo "Creating recovery-master-key secret..."

kubectl create secret generic recovery-master-key \
    --namespace=argocd \
    --from-literal=recovery-key.txt="$RECOVERY_PRIVATE_KEY" \
    --dry-run=client -o yaml | kubectl apply -f - > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Secret recovery-master-key created/updated"
else
    echo "ERROR: Failed to create recovery-master-key secret" >&2
    exit 1
fi

echo ""
echo "Summary"
echo "======="
echo ""
echo "✓ Recovery master key generated"
echo "✓ Age private key encrypted"
echo "✓ Backup secrets created in argocd namespace"
echo ""
echo "Secrets created:"
echo "  - age-backup-encrypted (encrypted Age private key)"
echo "  - recovery-master-key (recovery master key)"
echo ""
echo "Backup Retrieval Process"
echo "========================"
echo ""
echo "To manually recover the Age private key:"
echo ""
echo "1. Extract the recovery master key:"
echo "   kubectl get secret recovery-master-key -n argocd -o jsonpath='{.data.recovery-key\.txt}' | base64 -d > recovery-key.txt"
echo ""
echo "2. Extract the encrypted Age key:"
echo "   kubectl get secret age-backup-encrypted -n argocd -o jsonpath='{.data.encrypted-key\.txt}' | base64 -d > encrypted-age-key.txt"
echo ""
echo "3. Decrypt the Age private key:"
echo "   age -d -i recovery-key.txt encrypted-age-key.txt"
echo ""
echo "4. Inject the decrypted key back into the cluster:"
echo "   export AGE_PRIVATE_KEY=\$(age -d -i recovery-key.txt encrypted-age-key.txt)"
echo "   ./inject-age-key.sh"
echo ""
echo "⚠️  IMPORTANT: Store the recovery master key securely offline!"
echo "   Recovery Public Key: $RECOVERY_PUBLIC_KEY"
echo ""

exit 0
