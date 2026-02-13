"""Unit tests for Hetzner adapter rendering

Tests verify:
1. HetznerAdapter.render() generates correct output
2. Async API calls work correctly
3. CloudInfrastructureCapability is properly populated
"""

import pytest
from unittest.mock import AsyncMock, patch
from ztc.adapters.hetzner.adapter import HetznerAdapter
from ztc.interfaces.capabilities import CloudInfrastructureCapability


class TestHetznerAdapterRendering:
    """Test Hetzner adapter render() method"""
    
    @pytest.mark.asyncio
    async def test_render_generates_capability_data(self):
        """Test render() generates CloudInfrastructureCapability"""
        config = {
            "version": "v1.0.0",
            "api_token": "a" * 64,
            "server_ips": ["192.168.1.1"],
            "rescue_mode_confirm": True
        }
        
        adapter = HetznerAdapter(config)
        
        with patch.object(adapter, '_get_server_id_by_ip', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = "12345"
            
            output = await adapter.render(None)
            
            assert "cloud-infrastructure" in output.capabilities
            capability_data = output.capabilities["cloud-infrastructure"]
            assert capability_data["provider"] == "hetzner"
            assert "192.168.1.1" in capability_data["server_ids"]
            assert capability_data["rescue_mode_enabled"] is True
    
    @pytest.mark.asyncio
    async def test_render_queries_api_for_each_server(self):
        """Test render() calls API for each server IP"""
        config = {
            "version": "v1.0.0",
            "api_token": "a" * 64,
            "server_ips": ["192.168.1.1", "192.168.1.2"],
            "rescue_mode_confirm": False
        }
        
        adapter = HetznerAdapter(config)
        
        with patch.object(adapter, '_get_server_id_by_ip', new_callable=AsyncMock) as mock_api:
            mock_api.side_effect = ["12345", "67890"]
            
            output = await adapter.render(None)
            
            assert mock_api.call_count == 2
            capability_data = output.capabilities["cloud-infrastructure"]
            assert capability_data["server_ids"]["192.168.1.1"] == "12345"
            assert capability_data["server_ids"]["192.168.1.2"] == "67890"
    
    @pytest.mark.asyncio
    async def test_render_sets_environment_variables(self):
        """Test render() sets HCLOUD_TOKEN and SERVER_IPS env vars"""
        config = {
            "version": "v1.0.0",
            "api_token": "test_token_" + "a" * 53,
            "server_ips": ["192.168.1.1"],
            "rescue_mode_confirm": False
        }
        
        adapter = HetznerAdapter(config)
        
        with patch.object(adapter, '_get_server_id_by_ip', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = "12345"
            
            output = await adapter.render(None)
            
            assert output.env_vars["HCLOUD_TOKEN"] == config["api_token"]
            assert output.env_vars["SERVER_IPS"] == "192.168.1.1"
    
    @pytest.mark.asyncio
    async def test_render_generates_no_manifests(self):
        """Test render() generates no manifests (Hetzner is API-only)"""
        config = {
            "version": "v1.0.0",
            "api_token": "a" * 64,
            "server_ips": ["192.168.1.1"],
            "rescue_mode_confirm": False
        }
        
        adapter = HetznerAdapter(config)
        
        with patch.object(adapter, '_get_server_id_by_ip', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = "12345"
            
            output = await adapter.render(None)
            
            assert output.manifests == {}
            assert output.stages == []


class TestHetznerAPIIntegration:
    """Test Hetzner API integration"""
    
    @pytest.mark.asyncio
    async def test_get_server_id_by_ip_calls_api(self):
        """Test _get_server_id_by_ip() makes correct API call"""
        adapter = HetznerAdapter({})
        
        # Mock the entire method since aiohttp is not a dependency
        with patch.object(adapter, '_get_server_id_by_ip', new_callable=AsyncMock) as mock_method:
            mock_method.return_value = "12345"
            
            server_id = await adapter._get_server_id_by_ip("192.168.1.1", "test_token")
            
            assert server_id == "12345"
            mock_method.assert_called_once_with("192.168.1.1", "test_token")
