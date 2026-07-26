"""
GameTDB asset handler for game metadata and cover art.

Optional integration: reads API key from local config if present.
If no key is configured, falls back to other handlers.
"""

import requests
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import quote

logger = logging.getLogger(__name__)


class GameTDBHandler:
    """
    GameTDB API client for fetching cover art and metadata.
    Opt-in: requires explicit API key in config.
    """

    BASE_URL = "https://www.gametdb.com/api"
    TIMEOUT = 10
    RETRIES = 3

    def __init__(self, api_key: Optional[str] = None, cache_dir: Optional[Path] = None):
        """
        Initialize GameTDB handler.

        Args:
            api_key: Optional GameTDB API key. If None, handler is disabled.
            cache_dir: Optional directory for caching cover art.
        """
        self.api_key = api_key
        self.cache_dir = cache_dir or Path.home() / ".config" / "vapor-rom-mgr" / "gametdb_cache"
        self.enabled = bool(api_key)

        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"GameTDB handler enabled (cache: {self.cache_dir})")
        else:
            logger.debug("GameTDB handler disabled (no API key)")

    def fetch_cover_art(self, game_title: str, platform: str = "NDS") -> Optional[bytes]:
        """
        Fetch cover art for a game.

        Args:
            game_title: Game title to search for
            platform: Platform code (NDS, GBA, NES, SNES, etc.)

        Returns:
            Image bytes if found, None otherwise.
        """
        if not self.enabled:
            logger.debug("GameTDB disabled; skipping cover art fetch")
            return None

        try:
            # Check cache first
            cache_path = self._get_cache_path(game_title, platform, "cover")
            if cache_path.exists():
                logger.debug(f"Cache hit for {game_title}")
                return cache_path.read_bytes()

            # Fetch from API with retries
            for attempt in range(self.RETRIES):
                try:
                    url = f"{self.BASE_URL}/GetArt.php"
                    params = {
                        "title": game_title,
                        "platform": platform,
                        "key": self.api_key,
                    }
                    resp = requests.get(url, params=params, timeout=self.TIMEOUT)
                    resp.raise_for_status()

                    if resp.content:
                        # Cache and return
                        cache_path.parent.mkdir(parents=True, exist_ok=True)
                        cache_path.write_bytes(resp.content)
                        logger.info(f"Fetched cover art for {game_title} from GameTDB")
                        return resp.content
                    else:
                        logger.debug(f"No cover art found for {game_title}")
                        return None

                except requests.Timeout:
                    if attempt < self.RETRIES - 1:
                        logger.warning(f"GameTDB timeout (attempt {attempt + 1}/{self.RETRIES})")
                        continue
                    else:
                        raise

        except Exception as e:
            logger.error(f"Failed to fetch cover art from GameTDB: {e}")
            return None

    def fetch_metadata(self, game_title: str, platform: str = "NDS") -> Optional[Dict[str, Any]]:
        """
        Fetch game metadata from GameTDB.

        Args:
            game_title: Game title to search for
            platform: Platform code

        Returns:
            Metadata dict if found, None otherwise.
        """
        if not self.enabled:
            return None

        try:
            url = f"{self.BASE_URL}/GetGameXML.php"
            params = {
                "title": game_title,
                "platform": platform,
                "key": self.api_key,
            }
            resp = requests.get(url, params=params, timeout=self.TIMEOUT)
            resp.raise_for_status()

            # Parse XML response (simplified; full parsing would use xml.etree)
            if resp.content:
                logger.debug(f"Fetched metadata for {game_title}")
                return {"raw_xml": resp.text}
            return None

        except Exception as e:
            logger.error(f"Failed to fetch metadata from GameTDB: {e}")
            return None

    def _get_cache_path(
        self, game_title: str, platform: str, asset_type: str
    ) -> Path:
        """
        Generate cache path for asset.

        Args:
            game_title: Game title (used in filename)
            platform: Platform code
            asset_type: Type of asset (cover, banner, icon, etc.)

        Returns:
            Path object for cache file.
        """
        safe_title = quote(game_title, safe="")
        filename = f"{platform}_{asset_type}_{safe_title}.png"
        return self.cache_dir / filename

    def clear_cache(self) -> None:
        """Clear all cached assets."""
        import shutil
        try:
            shutil.rmtree(self.cache_dir)
            logger.info("GameTDB cache cleared")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
