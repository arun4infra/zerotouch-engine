"""Crossplane adapter for ZTC engine.

This adapter provides infrastructure provisioning capabilities via Crossplane operator.
It installs Crossplane into a Kubernetes cluster via ArgoCD and configures cloud providers
(Kubernetes, AWS, Hetzner) based on infrastructure context.
"""

from ztc.adapters.crossplane.adapter import CrossplaneAdapter

__all__ = ["CrossplaneAdapter"]
