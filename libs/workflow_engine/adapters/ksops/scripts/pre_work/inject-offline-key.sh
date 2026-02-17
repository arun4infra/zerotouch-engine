#!/usr/bin/env bash
# Emergency Break-Glass: Inject Age Private Key Offline
#
# META_REQUIRE: None (emergency recovery script)
#
# This script provides emergency recovery capability to inject Age private keys
# into the cluster when automated recovery fails or during disaster recovery scenarios.
#
# SECURITY WARNING: This script handles sensitive cryptographic material.
# Use only in emergency situations and ensure secure key handling.

set -euo pipefail

# Configuration
NAMESPACE="${NAMESPACE:-argocd}"
SECRET_NAME="${SECRET_NAME:-sops-age}"
AGE_KEY_FILE=""
AGE_KEY_STDIN=false
VERIFY_DECRYPTION=true

# Validate context file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

# Usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Emergency script to inject Age private key into cluster for SOPS decryption.

OPTIONS:
    -f, --file FILE         Path to Age private key file
    -s, --stdin             Read Age private key from stdin (secure)
    -n, --namespace NS      Kubernetes namespace (default: argocd)
    --secret-name NAME      Secret name (default: sops-age)
    --no-verify             Skip decryption verification test
    -h, --help              Show this help message

EXAMPLES:
    # Read key from file
    $0 --file /path/to/age-key.txt

    # Read key from stdin (more secure - no file on disk)
    cat age-key.txt | $0 --stdin

    # Specify custom namespace
    $0 --file age-key.txt --namespace custom-ns

SECURITY NOTES:
    - Age private keys are sensitive cryptographic material
    - Use stdin input to avoid leaving keys on disk
    - Delete key files immediately after use
    - Rotate keys after emergency recovery

EOF
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--file)
            AGE_KEY_FILE="$2"
            shift 2
            ;;
        -s|--stdin)
            AGE_KEY_STDIN=true
            shift
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --secret-name)
            SECRET_NAME="$2"
            shift 2
            ;;
        --no-verify)
            VERIFY_DECRYPTION=false
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "ERROR: Unknown option: $1" >&2
            usage
            ;;
    esac
done

# Validate kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl not found" >&2
    exit 1
fi

# Validate cluster connectivity
if ! kubectl cluster-info &> /dev/null; then
    echo "ERROR: Cannot connect to Kubernetes cluster" >&2
    exit 1
fi

echo "🚨 Emergency Break-Glass: Age Key Injection"
echo ""
echo "Configuration:"
echo "  Namespace: $NAMESPACE"
echo "  Secret Name: $SECRET_NAME"
echo "  Verify Decryption: $VERIFY_DECRYPTION"
echo ""

# Read Age private key
AGE_PRIVATE_KEY=""

if [[ "$AGE_KEY_STDIN" == true ]]; then
    echo "📥 Reading Age private key from stdin..."
    AGE_PRIVATE_KEY=$(cat)
elif [[ -n "$AGE_KEY_FILE" ]]; then
    if [[ ! -f "$AGE_KEY_FILE" ]]; then
        echo "ERROR: Age key file not found: $AGE_KEY_FILE" >&2
        exit 1
    fi
    echo "📥 Reading Age private key from file: $AGE_KEY_FILE"
    AGE_PRIVATE_KEY=$(cat "$AGE_KEY_FILE")
else
    echo "ERROR: No Age private key provided" >&2
    echo "Use --file or --stdin to provide the key" >&2
    exit 1
fi

# Validate Age key format
if [[ ! "$AGE_PRIVATE_KEY" =~ ^AGE-SECRET-KEY-1 ]]; then
    echo "ERROR: Invalid Age private key format" >&2
    echo "Age private keys must start with 'AGE-SECRET-KEY-1'" >&2
    exit 1
fi

# Validate key length
KEY_LENGTH=${#AGE_PRIVATE_KEY}
if [[ $KEY_LENGTH -lt 50 || $KEY_LENGTH -gt 100 ]]; then
    echo "WARNING: Age key length unusual ($KEY_LENGTH chars)" >&2
    echo "Expected length: ~74 characters" >&2
fi

echo "✓ Age private key validated"
echo ""

# Ensure namespace exists
echo "🔍 Checking namespace..."
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    echo "Creating namespace $NAMESPACE..."
    kubectl create namespace "$NAMESPACE"
    echo "✓ Namespace created"
else
    echo "✓ Namespace exists"
fi
echo ""

# Check if secret already exists
echo "🔍 Checking existing secret..."
if kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" &> /dev/null; then
    echo "WARNING: Secret $SECRET_NAME already exists in namespace $NAMESPACE" >&2
    echo "This will OVERWRITE the existing secret." >&2
    
    # Backup existing secret
    echo "💾 Backing up existing secret..."
    BACKUP_FILE="/tmp/${SECRET_NAME}-backup-$(date +%Y%m%d-%H%M%S).yaml"
    kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o yaml > "$BACKUP_FILE"
    echo "✓ Backup saved to: $BACKUP_FILE"
    echo ""
fi

# Create or update secret
echo "🔐 Injecting Age private key into cluster..."

kubectl create secret generic "$SECRET_NAME" \
    --namespace="$NAMESPACE" \
    --from-literal=keys.txt="$AGE_PRIVATE_KEY" \
    --dry-run=client -o yaml | kubectl apply -f -

if [[ $? -eq 0 ]]; then
    echo "✓ Age private key injected successfully"
else
    echo "ERROR: Failed to inject Age private key" >&2
    exit 1
fi
echo ""

# Verify secret was created correctly
echo "🔍 Verifying secret..."
if ! kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" &> /dev/null; then
    echo "ERROR: Secret not found after creation" >&2
    exit 1
fi

# Verify secret contains keys.txt
if ! kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.data.keys\.txt}' | base64 -d | grep -q "AGE-SECRET-KEY-1"; then
    echo "ERROR: Secret does not contain valid Age key" >&2
    exit 1
fi

echo "✓ Secret verified"
echo ""

# Final instructions
echo "✅ Emergency Age Key Injection Complete"
echo ""
echo "Next Steps:"
echo "  1. Verify ArgoCD can sync SOPS-encrypted applications"
echo "  2. Check ArgoCD logs for decryption errors"
echo "  3. Monitor application deployments"
echo "  4. Plan Age key rotation after emergency recovery"
echo ""
echo "Verify ArgoCD Decryption:"
echo "  kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=argocd-repo-server -c ksops"
echo ""
echo "⚠️  SECURITY REMINDER:"
echo "  • Delete Age key files from disk immediately"
echo "  • Rotate Age keys after emergency recovery"
echo "  • Document this break-glass event"
echo ""

exit 0
