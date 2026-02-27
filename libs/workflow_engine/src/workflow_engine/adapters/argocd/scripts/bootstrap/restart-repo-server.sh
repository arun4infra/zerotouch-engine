#!/usr/bin/env bash
# Restart ArgoCD repo-server to pick up Age key secret
#
# META_REQUIRE: None

set -euo pipefail

echo "Restarting ArgoCD repo-server to mount Age key..."

kubectl rollout restart deployment argocd-repo-server -n argocd

echo "Waiting for repo-server to be ready..."
kubectl rollout status deployment argocd-repo-server -n argocd --timeout=120s

echo "✓ ArgoCD repo-server restarted successfully"
