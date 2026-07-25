"""
Base class for asset handlers.

Handles fetching and generating game icons, banners, and cover art
from various sources (PicoCover, local files, web searches, etc.).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pathlib import Path
from vapor.core.logger import setup_logger

logger = setup_logger(__name__)


class AssetFetchError(Exception):
    """Error fetching or generating assets."""
    pass


class AssetHandler(ABC):
    """
    Abstract base class for asset sources and handlers.

    Asset handlers are responsible for:
    - Fetching/searching for game art
    - Converting/generating assets in system-specific formats
    - Managing cached assets
    """

    def __init__(self, cache_dir: Path = None):
        """
        Initialize asset handler.

        Args:
            cache_dir: Directory to cache downloaded/generated assets
        """
        self.cache_dir = cache_dir or Path("./assets")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = setup_logger(f"vapor.assets.{self.__class__.__name__}")

    @property
    @abstractmethod
    def handler_name(self) -> str:
        """Return handler name (e.g., 'PicoCover', 'DuckDuckGo', 'Local')."""
        pass

    @abstractmethod
    def fetch_cover_art(self, rom_title: str, series: str = None) -> Optional[bytes]:
        """
        Fetch cover art for a ROM.

        Args:
            rom_title: Game title to search for
            series: Optional series name (e.g., 'Pokemon', 'Zelda')

        Returns:
            Image bytes if found, None otherwise.
        """
        pass

    @abstractmethod
    def fetch_banner(self, rom_title: str, series: str = None) -> Optional[bytes]:
        """
        Fetch banner art for a ROM (system-specific format).

        Args:
            rom_title: Game title to search for
            series: Optional series name

        Returns:
            Banner bytes if found, None otherwise.
        """
        pass

    @abstractmethod
    def fetch_icon(self, rom_title: str, series: str = None) -> Optional[bytes]:
        """
        Fetch icon for a ROM (system-specific format).

        Args:
            rom_title: Game title to search for
            series: Optional series name

        Returns:
            Icon bytes if found, None otherwise.
        """
        pass

    @abstractmethod
    def supports_rom_hacks(self) -> bool:
        """
        Return whether this handler supports ROM hacks/fan games.

        Some handlers (like PicoCover) only have official game data.

        Returns:
            True if handler can find assets for ROM hacks.
        """
        pass

    def cache_hit(self, cache_key: str) -> Optional[bytes]:
        """
        Check if asset is already cached.

        Args:
            cache_key: Cache key (e.g., "pokemon-emerald-icon")

        Returns:
            Cached asset bytes if found, None otherwise.
        """
        cache_file = self.cache_dir / f"{cache_key}.bin"
        if cache_file.exists():
            return cache_file.read_bytes()
        return None

    def cache_asset(self, cache_key: str, asset_bytes: bytes) -> Path:
        """
        Cache an asset.

        Args:
            cache_key: Cache key
            asset_bytes: Asset data to cache

        Returns:
            Path to cached file.
        """
        cache_file = self.cache_dir / f"{cache_key}.bin"
        cache_file.write_bytes(asset_bytes)
        return cache_file
