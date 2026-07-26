"""
Unit tests for GameTDB asset handler.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

from vapor.assets.gametdb import GameTDBHandler


class TestGameTDBHandler:
    """Test GameTDB asset handler."""

    def test_handler_disabled_without_key(self) -> None:
        """Test that handler is disabled without API key."""
        handler = GameTDBHandler(api_key=None)
        assert not handler.enabled

    def test_handler_enabled_with_key(self) -> None:
        """Test that handler is enabled with API key."""
        handler = GameTDBHandler(api_key="test-key-123")
        assert handler.enabled
        assert handler.api_key == "test-key-123"

    def test_cache_dir_creation(self) -> None:
        """Test that cache directory is created when enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "gametdb_cache"
            handler = GameTDBHandler(api_key="test-key", cache_dir=cache_dir)
            assert cache_dir.exists()

    def test_fetch_cover_art_disabled(self) -> None:
        """Test that cover art fetch returns None when disabled."""
        handler = GameTDBHandler(api_key=None)
        result = handler.fetch_cover_art("Pokemon Red")
        assert result is None

    @patch("vapor.assets.gametdb.requests.get")
    def test_fetch_cover_art_success(self, mock_get: MagicMock) -> None:
        """Test successful cover art fetch."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.content = b"fake image data"
        mock_get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            handler = GameTDBHandler(api_key="test-key", cache_dir=Path(tmpdir))
            result = handler.fetch_cover_art("Pokemon Red", platform="GBA")

            assert result == b"fake image data"
            mock_get.assert_called_once()

    @patch("vapor.assets.gametdb.requests.get")
    def test_fetch_cover_art_caching(self, mock_get: MagicMock) -> None:
        """Test that cover art is cached on second fetch."""
        mock_response = MagicMock()
        mock_response.content = b"cached image"
        mock_get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            handler = GameTDBHandler(api_key="test-key", cache_dir=Path(tmpdir))

            # First fetch
            result1 = handler.fetch_cover_art("Zelda", platform="NDS")
            assert result1 == b"cached image"
            assert mock_get.call_count == 1

            # Second fetch (should use cache)
            result2 = handler.fetch_cover_art("Zelda", platform="NDS")
            assert result2 == b"cached image"
            # Mock should not be called again
            assert mock_get.call_count == 1

    @patch("vapor.assets.gametdb.requests.get")
    def test_fetch_cover_art_not_found(self, mock_get: MagicMock) -> None:
        """Test handling of missing cover art."""
        mock_response = MagicMock()
        mock_response.content = b""
        mock_get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            handler = GameTDBHandler(api_key="test-key", cache_dir=Path(tmpdir))
            result = handler.fetch_cover_art("NonExistentGame")
            assert result is None

    @patch("vapor.assets.gametdb.requests.get")
    def test_fetch_cover_art_timeout_retry(self, mock_get: MagicMock) -> None:
        """Test retry logic on timeout."""
        import requests

        # First two calls raise timeout, third succeeds
        mock_response = MagicMock()
        mock_response.content = b"success"
        mock_get.side_effect = [
            requests.Timeout(),
            requests.Timeout(),
            mock_response,
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            handler = GameTDBHandler(api_key="test-key", cache_dir=Path(tmpdir))
            result = handler.fetch_cover_art("Robust Game")
            assert result == b"success"
            assert mock_get.call_count == 3

    @patch("vapor.assets.gametdb.requests.get")
    def test_fetch_cover_art_max_retries_exceeded(self, mock_get: MagicMock) -> None:
        """Test that max retries is respected."""
        import requests

        mock_get.side_effect = requests.Timeout()

        with tempfile.TemporaryDirectory() as tmpdir:
            handler = GameTDBHandler(api_key="test-key", cache_dir=Path(tmpdir))
            result = handler.fetch_cover_art("Timeout Game")
            assert result is None
            assert mock_get.call_count == handler.RETRIES

    def test_fetch_metadata_disabled(self) -> None:
        """Test that metadata fetch returns None when disabled."""
        handler = GameTDBHandler(api_key=None)
        result = handler.fetch_metadata("Pokemon Red")
        assert result is None

    @patch("vapor.assets.gametdb.requests.get")
    def test_fetch_metadata_success(self, mock_get: MagicMock) -> None:
        """Test successful metadata fetch."""
        mock_response = MagicMock()
        mock_response.text = "<game>...</game>"
        mock_response.content = b"<game>...</game>"
        mock_get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            handler = GameTDBHandler(api_key="test-key", cache_dir=Path(tmpdir))
            result = handler.fetch_metadata("Pokemon Red", platform="GBA")

            assert result is not None
            assert "raw_xml" in result

    def test_clear_cache(self) -> None:
        """Test cache clearing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            handler = GameTDBHandler(api_key="test-key", cache_dir=cache_dir)

            # Create a dummy file in cache
            (cache_dir / "dummy.png").write_text("test")
            assert cache_dir.exists()

            # Clear cache
            handler.clear_cache()
            assert not cache_dir.exists()
