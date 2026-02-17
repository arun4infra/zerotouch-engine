"""ArgoCD adapter for ZTC engine.

This adapter provides ArgoCD installation and bootstrap functionality,
migrating from the legacy zerotouch-platform Bash-based system.
"""

from workflow_engine.adapters.argocd.adapter import ArgocdAdapter

__all__ = ["ArgocdAdapter"]
