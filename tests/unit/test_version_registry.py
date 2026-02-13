"""Unit tests for VersionRegistry"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from ztc.registry.versions import VersionRegistry


@pytest.fixture
def version_registry():
    """Create VersionRegistry instance for testing"""
    return VersionRegistry()


def test_load_embedded_versions(version_registry):
    """Test loading embedded versions.yaml"""
    versions = version_registry.load_embedded_versions()
    
    assert "components" in versions
    assert "talos" in versions["components"]
    assert "cilium" in versions["components"]
    assert "hetzner" in versions["components"]


def test_get_versions_returns_embedded(version_registry):
    """Test get_versions returns embedded versions"""
    versions = version_registry.get_versions()
    
    assert versions == version_registry.embedded_versions
    assert "components" in versions


def test_get_supported_versions(version_registry):
    """Test getting supported versions for component"""
    talos_versions = version_registry.get_supported_versions("talos")
    
    assert isinstance(talos_versions, list)
    assert "v1.11.5" in talos_versions


def test_get_supported_versions_missing_component(version_registry):
    """Test getting supported versions for missing component raises KeyError"""
    with pytest.raises(KeyError):
        version_registry.get_supported_versions("nonexistent")


def test_get_default_version(version_registry):
    """Test getting default version for component"""
    default = version_registry.get_default_version("talos")
    
    assert default == "v1.11.5"


def test_get_default_version_missing_component(version_registry):
    """Test getting default version for missing component raises KeyError"""
    with pytest.raises(KeyError):
        version_registry.get_default_version("nonexistent")


def test_get_artifact(version_registry):
    """Test getting artifact for specific version"""
    factory_id = version_registry.get_artifact("talos", "v1.11.5", "factory_image_id")
    
    assert isinstance(factory_id, str)
    assert len(factory_id) == 64


def test_get_artifact_missing_component(version_registry):
    """Test getting artifact for missing component raises KeyError"""
    with pytest.raises(KeyError):
        version_registry.get_artifact("nonexistent", "v1.0", "key")


def test_get_artifact_missing_version(version_registry):
    """Test getting artifact for missing version raises KeyError"""
    with pytest.raises(KeyError):
        version_registry.get_artifact("talos", "v99.99.99", "factory_image_id")


def test_get_version_source_default(version_registry):
    """Test version source defaults to embedded"""
    assert version_registry.get_version_source() == "embedded"


def test_get_last_error_default(version_registry):
    """Test last error defaults to None"""
    assert version_registry.get_last_error() is None


@pytest.mark.asyncio
async def test_get_versions_async_timeout(version_registry):
    """Test get_versions_async falls back on timeout"""
    async def slow_fetch():
        await asyncio.sleep(10)
        return None
    
    with patch.object(version_registry, '_fetch_remote_async', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = slow_fetch
        
        versions = await version_registry.get_versions_async(timeout=0.1)
        
        assert versions == version_registry.embedded_versions
        assert "timeout" in version_registry.get_version_source()
        assert version_registry.get_last_error() is not None


@pytest.mark.asyncio
async def test_get_versions_async_remote_success(version_registry):
    """Test get_versions_async uses remote on success"""
    remote_versions = {
        "components": {
            "talos": {
                "supported_versions": ["v1.12.0"],
                "default_version": "v1.12.0"
            }
        }
    }
    
    with patch.object(version_registry, '_fetch_remote_async', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = remote_versions
        
        versions = await version_registry.get_versions_async(timeout=2.0)
        
        assert "talos" in versions["components"]
        assert version_registry.get_version_source() == "remote"


@pytest.mark.asyncio
async def test_get_versions_async_remote_none(version_registry):
    """Test get_versions_async falls back when remote returns None"""
    with patch.object(version_registry, '_fetch_remote_async', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = None
        
        versions = await version_registry.get_versions_async(timeout=2.0)
        
        assert versions == version_registry.embedded_versions


def test_merge_versions(version_registry):
    """Test merging remote versions with embedded"""
    embedded = {
        "components": {
            "talos": {"version": "v1.11.5"},
            "cilium": {"version": "v1.18.5"}
        }
    }
    
    remote = {
        "components": {
            "talos": {"version": "v1.12.0"},
            "new_component": {"version": "v1.0.0"}
        }
    }
    
    merged = version_registry._merge_versions(embedded, remote)
    
    assert merged["components"]["talos"]["version"] == "v1.12.0"
    assert merged["components"]["cilium"]["version"] == "v1.18.5"
    assert merged["components"]["new_component"]["version"] == "v1.0.0"


def test_load_public_key_missing(version_registry):
    """Test load_public_key returns None when key file missing"""
    with patch.object(Path, 'exists', return_value=False):
        key = version_registry.load_public_key()
        assert key is None


def test_verify_signature_no_public_key(version_registry):
    """Test signature verification fails without public key"""
    version_registry.public_key = None
    
    result = version_registry._verify_signature(b"content", b"signature")
    
    assert result is False


@pytest.mark.asyncio
async def test_fetch_remote_async_no_url(version_registry):
    """Test fetch returns None when no remote URL configured"""
    version_registry.embedded_versions = {"components": {}}
    
    result = await version_registry._fetch_remote_async()
    
    assert result is None
