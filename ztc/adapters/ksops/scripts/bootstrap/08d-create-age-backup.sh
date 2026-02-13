#!/usr/bin/env bash
# Create Age Key Backup for Automated Recovery
#
# META_REQUIRE: None

set -euo pipefail

# Validate context file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

echo "Age Key Backup Creation for Disaster Recovery"
echo "=============================================="
echo ""

# Check if sops-age secret exists
if ! kubectl get secret sops-age -n argocd &>/dev/null; then
    echo "ERROR: sops-age secret not found" >&2
    echo "Run 08c-inject-age-key.sh first" >&2
    exit 1
fi

echo "✓ sops-age secret found"
echo ""

# Generate recovery master key
echo "Generating recovery master key..."
RECOVERY_KEY=$(age-keygen 2>/dev/null)
RECOVERY_PUBLIC=$(echo "$RECOVERY_KEY" | grep "public key:" | cut -d: -f2 | xargs)
RECOVERY_PRIVATE=$(echo "$RECOVERY_KEY" | grep "AGE-SECRET-KEY-" | xargs)

echo "✓ Recovery master key generated"
echo "Recovery public key: $RECOVERY_PUBLIC"
echo ""

# Extract Age private key from sops-age secret
echo "Extracting Age private key..."
AGE_PRIVATE_KEY=$(kubectl get secret sops-age -n argocd -o jsonpath='{.data.keys\.txt}' | base64 -d)
echo "✓ Age private key extracted"
echo ""

# Encrypt Age private key with recovery master key
echo "Encrypting Age private key with recovery master key..."
ENCRYPTED_BACKUP=$(echo "$AGE_PRIVATE_KEY" | age -r "$RECOVERY_PUBLIC" -a)
echo "✓ Age private key encrypted"
echo ""

# Create age-backup-encrypted secret
echo "Creating age-backup-encrypted secret..."
kubectl create secret generic age-backup-encrypted \
    --from-literal=encrypted-key.txt="$ENCRYPTED_BACKUP" \
    --namespace=argocd \
    --dry-run=client -o yaml | kubectl apply -f -
echo "✓ age-backup-encrypted secret created"
echo ""

# Create recovery-master-key secret
echo "Creating recovery-master-key secret..."
kubectl create secret generic recovery-master-key \
    --from-literal=recovery-key.txt="$RECOVERY_PRIVATE" \
    --namespace=argocd \
    --dry-run=client -o yaml | kubectl apply -f -
echo "✓ recovery-master-key secret created"
echo ""

echo "Backup Summary"
echo "=============="
echo ""
echo "✓ Age key backup created successfully"
echo "✓ Secret: age-backup-encrypted (encrypted Age key)"
echo "✓ Secret: recovery-master-key (recovery key)"
echo ""
echo "IMPORTANT: Store recovery master key securely offline"
echo "Recovery public key: $RECOVERY_PUBLIC"
echo ""
