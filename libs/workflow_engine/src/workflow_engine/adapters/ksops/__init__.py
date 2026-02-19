"""KSOPS adapter for secrets management with SOPS and Age encryption."""

from .adapter import KSOPSAdapter
from .output import KSOPSOutputData

__all__ = ["KSOPSAdapter", "KSOPSOutputData"]
