"""Version registry for managing component versions."""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp
import yaml
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key

logger = logging.getLogger(__name__)


class VersionRegistry:
    """Registry for managing component versions with embedded fallback."""

    def __init__(self):
        self.embedded_versions = self.load_embedded_versions()
        self.remote_versions = None
        self.public_key = self.load_public_key()
        self._fetch_task = None
        self._last_error = None
        self._version_source = "embedded"

    def load_embedded_versions(self) -> Dict:
        """Load versions.yaml embedded in CLI binary."""
        versions_path = Path(__file__).parent.parent / "versions.yaml"
        return yaml.safe_load(versions_path.read_text())

    def load_public_key(self):
        """Load public key for signature verification."""
        key_path = Path(__file__).parent.parent / "ztc_public_key.pem"
        if not key_path.exists():
            return None
        return load_pem_public_key(key_path.read_bytes())

    def get_versions(self) -> Dict:
        """Synchronous version getter (uses embedded only, no blocking)."""
        return self.embedded_versions

    def get_version_source(self) -> str:
        """Get the source of versions used (for user transparency)."""
        return self._version_source

    def get_last_error(self) -> Optional[str]:
        """Get last version fetch error for display in CLI summary."""
        return self._last_error

    def get_supported_versions(self, component: str) -> List[str]:
        """Get supported versions for component.

        Raises:
            KeyError: If component not found in versions.yaml
        """
        versions = self.get_versions()
        return versions["components"][component]["supported_versions"]

    def get_default_version(self, component: str) -> str:
        """Get default version for component.

        Raises:
            KeyError: If component not found in versions.yaml
        """
        versions = self.get_versions()
        return versions["components"][component]["default_version"]

    def get_artifact(self, component: str, version: str, artifact_key: str) -> str:
        """Get artifact URL/SHA for specific version.

        Raises:
            KeyError: If component, version, or artifact_key not found
        """
        versions = self.get_versions()
        return versions["components"][component]["artifacts"][version][artifact_key]

    def start_background_fetch(self):
        """Start non-blocking background fetch of remote versions.

        CRITICAL: This creates a task but does NOT guarantee completion.
        Always call get_versions_async() with explicit await to ensure deterministic behavior.
        """
        if self._fetch_task is None:
            self._fetch_task = asyncio.create_task(self._fetch_remote_async())

    async def _fetch_remote_async(self) -> Optional[Dict]:
        """Async fetch and verify remote versions.yaml."""
        try:
            remote_url = self.embedded_versions.get("remote_versions_url")
            sig_url = self.embedded_versions.get("remote_versions_signature_url")

            if not remote_url:
                logger.debug("No remote_versions_url configured")
                return None

            async with aiohttp.ClientSession() as session:
                async with session.get(remote_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    response.raise_for_status()
                    versions_content = await response.read()

                async with session.get(sig_url, timeout=aiohttp.ClientTimeout(total=5)) as sig_response:
                    sig_response.raise_for_status()
                    signature = await sig_response.read()

            if self._verify_signature(versions_content, signature):
                return yaml.safe_load(versions_content)
            else:
                logger.warning("Remote versions signature verification failed")
                return None

        except aiohttp.ClientError as e:
            logger.debug(f"Network error fetching remote versions: {e}")
            return None
        except Exception as e:
            logger.debug(f"Unexpected error fetching remote versions: {e}")
            return None

    def _verify_signature(self, content: bytes, signature: bytes) -> bool:
        """Verify cryptographic signature of remote versions file."""
        if not self.public_key:
            logger.debug("No public key available for signature verification")
            return False

        try:
            self.public_key.verify(
                signature,
                content,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception as e:
            logger.debug(f"Signature verification failed: {e}")
            return False

    async def get_versions_async(self, timeout: float = 2.0) -> Dict:
        """Get versions with explicit await on remote fetch (correctness-first).

        Args:
            timeout: Max time to wait for remote fetch (default 2s)

        Returns:
            Merged versions (remote + embedded) if remote succeeds, embedded-only on timeout/failure

        Behavior:
            - If fetch task not started, starts it and awaits with timeout
            - If fetch task already running, awaits its completion with timeout
            - On timeout/failure, falls back to embedded versions with explicit user notification
            - Tracks version source for transparency (self._version_source)

        Correctness Guarantee:
            User is explicitly notified which version source is used, preventing silent
            inconsistencies across team members due to network conditions.
        """
        if self._fetch_task is None:
            self._fetch_task = asyncio.create_task(self._fetch_remote_async())

        try:
            remote = await asyncio.wait_for(self._fetch_task, timeout=timeout)
            if remote:
                logger.info("Successfully fetched remote versions")
                self._version_source = "remote"
                return self._merge_versions(self.embedded_versions, remote)
        except asyncio.TimeoutError:
            logger.warning(f"Version check timed out after {timeout}s - using embedded fallback")
            self._last_error = f"Timeout after {timeout}s"
            self._version_source = "embedded (timeout)"
        except Exception as e:
            logger.warning(f"Version check failed ({type(e).__name__}: {e}) - using embedded fallback")
            self._last_error = f"{type(e).__name__}: {e}"
            self._version_source = f"embedded (error: {type(e).__name__})"

        return self.embedded_versions

    def _merge_versions(self, embedded: Dict, remote: Dict) -> Dict:
        """Merge remote versions with embedded (remote takes precedence)."""
        merged = embedded.copy()

        for component, component_data in remote["components"].items():
            if component in merged["components"]:
                merged["components"][component].update(component_data)
            else:
                merged["components"][component] = component_data

        return merged
