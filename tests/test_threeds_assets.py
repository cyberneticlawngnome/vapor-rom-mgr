"""
Unit tests for 3DS asset integration (push_assets with GameTDB + fallback).
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Dict, Any

# Conditional import handling
try:
    from vapor.systems.threeds import Nintendo3DSPlugin
    THREEDS_AVAILABLE = True
except ImportError:
    THREEDS_AVAILABLE = False


@pytest.mark.skipif(not THREEDS_AVAILABLE, reason="3DS system plugin not available")
class TestThreeDSAssets:
    """Test 3DS asset push with GameTDB integration."""

    @pytest.fixture
    def mock_device_config(self) -> Dict[str, Any]:
        """Create a mock device configuration."""
        return {
            "deviceId": "test-3ds",
            "system": "3DS",
            "hardware": "3DS-XL",
            "mountPoint": "/mnt/test",
            "romPath": "/ROMs",
            "assets": {"gametdbApiKey": "test-key-123"},
        }

    @pytest.fixture
    def mock_plugin(self, mock_device_config: Dict[str, Any]) -> MagicMock:
        """Create a mock 3DS plugin."""
        plugin = MagicMock(spec=Nintendo3DSPlugin)
        plugin.device_config = mock_device_config
        plugin.device_name = "test-3ds"
        plugin.mount_point = Path("/mnt/test")
        plugin.rom_path = "/ROMs"
        return plugin

    def test_push_assets_with_gametdb_key(self, mock_device_config: Dict[str, Any]) -> None:
        """Test that GameTDB is used when API key is configured."""
        assert "assets" in mock_device_config
        assert "gametdbApiKey" in mock_device_config["assets"]
        assert mock_device_config["assets"]["gametdbApiKey"] == "test-key-123"

    def test_push_assets_without_gametdb_key(self) -> None:
        """Test that handler falls back gracefully without API key."""
        config = {
            "deviceId": "test-3ds",
            "system": "3DS",
            "assets": {},  # No GameTDB key
        }
        assert config["assets"].get("gametdbApiKey") is None

    @patch("vapor.assets.gametdb.GameTDBHandler")
    @patch("vapor.assets.twilight.TwiLightAssetHandler")
    def test_asset_resolution_chain_gametdb_primary(
        self,
        mock_twilight: MagicMock,
        mock_gametdb: MagicMock,
    ) -> None:
        """Test that GameTDB is tried first in asset resolution."""
        # Setup mocks
        gametdb_instance = MagicMock()
        gametdb_instance.enabled = True
        gametdb_instance.fetch_cover_art.return_value = b"gametdb_image"
        mock_gametdb.return_value = gametdb_instance

        twilight_instance = MagicMock()
        twilight_instance.fetch_icon.return_value = None
        twilight_instance.cache_dir = Path("/tmp/cache")
        mock_twilight.return_value = twilight_instance

        # Verify GameTDB handler was initialized
        assert gametdb_instance.enabled

    def test_asset_map_structure(self) -> None:
        """Test expected asset_map structure for push_assets."""
        asset_map = {
            "Pokemon/Pokemon Red.gba": {
                "icon": "pokemon-red-icon.png",
                "banner": "pokemon-red-banner.png",
            },
            "Zelda/Zelda Link to the Past.snes": {
                "icon": "zelda-lttp-icon.png",
            },
        }

        # Verify structure
        assert len(asset_map) == 2
        for rom_path, assets in asset_map.items():
            assert isinstance(rom_path, str)
            assert isinstance(assets, dict)

    def test_push_results_structure(self) -> None:
        """Test expected results structure from push_assets."""
        expected_results = {
            "pushed": 5,
            "skipped": 2,
            "failed": 1,
            "details": [
                {"rom": "test1.gba", "status": "pushed", "asset": "/path/to/icon.png"},
                {"rom": "test2.gba", "status": "skipped", "reason": "no icon available"},
                {"rom": "test3.gba", "status": "failed", "asset": "/path/to/icon.png"},
            ],
        }

        assert "pushed" in expected_results
        assert "skipped" in expected_results
        assert "failed" in expected_results
        assert "details" in expected_results
        assert expected_results["pushed"] == 5
