"""
Nintendo 3DS system plugin.

Supports: Original 3DS, 3DS XL, New 3DS, New 3DS XL

Detection methods:
- FTP: Connect via ftpd, inspect banner and SYST response
- SD Card: Check Nintendo 3DS folder structure and ID0/ID1 markers
"""

import ftplib
import socket
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from vapor.systems.base import SystemPlugin, SystemDetectionError
from vapor.core.logger import setup_logger

logger = setup_logger(__name__)


class Nintendo3DSPlugin(SystemPlugin):
    """Nintendo 3DS family system plugin."""

    @property
    def system_name(self) -> str:
        return "3DS"

    @property
    def supported_rom_types(self) -> List[str]:
        """Base 3DS supports NES, GB, GBC, GBA. XL adds SNES."""
        hardware = self.device_config.get("hardware", "3DS")
        if "XL" in hardware or "New" in hardware:
            return ["NES", "GB", "GBC", "GBA", "SNES"]
        return ["NES", "GB", "GBC", "GBA"]

    def detect(self) -> bool:
        """
        Detect 3DS via FTP or SD card.

        Returns:
            True if detected and accessible.

        Raises:
            SystemDetectionError: If detection fails unexpectedly.
        """
        connection_method = self.device_config.get("connectionMethod", "sd")

        if connection_method == "ftp":
            return self._detect_via_ftp()
        elif connection_method == "sd":
            return self._detect_via_sd_card()
        else:
            raise SystemDetectionError(f"Unknown connection method: {connection_method}")

    def _detect_via_ftp(self) -> bool:
        """Detect 3DS via FTP connection."""
        # TODO: Implement FTP detection
        # - Try to connect to ftpd on common ports
        # - Parse SYST response to determine model
        # - Cache result in device config
        logger.info("FTP detection not yet implemented")
        return False

    def _detect_via_sd_card(self) -> bool:
        """Detect 3DS via SD card filesystem markers."""
        try:
            # Look for Nintendo 3DS folder structure
            sd_root = self.mount_point
            nintendo_dir = sd_root / "Nintendo 3DS"

            if not nintendo_dir.exists():
                logger.warning(f"Nintendo 3DS folder not found at {nintendo_dir}")
                return False

            # Check for ID0 (32-char hex folder)
            id0_dirs = [d for d in nintendo_dir.iterdir() if d.is_dir() and len(d.name) == 32]

            if not id0_dirs:
                logger.warning("No valid ID0 folder found in Nintendo 3DS directory")
                return False

            logger.info(f"Found 3DS SD card with ID0: {id0_dirs[0].name}")

            # Detect hardware variant (New 3DS vs Old 3DS)
            hardware = self._detect_hardware_from_extdata(id0_dirs[0])
            if hardware:
                self.device_config["hardware"] = hardware
                logger.info(f"Detected hardware: {hardware}")

            return True

        except Exception as e:
            raise SystemDetectionError(f"Failed to detect 3DS via SD card: {e}")

    def _detect_hardware_from_extdata(self, id0_path: Path) -> Optional[str]:
        """
        Determine if New 3DS or Old 3DS by checking extdata markers.

        New 3DS has exclusive title IDs like 0x00000219, 0x00000220.

        Args:
            id0_path: Path to ID0 directory

        Returns:
            Hardware string ("3DS", "3DS-XL", "New 3DS", "New 3DS XL") or None
        """
        # TODO: Implement extdata checking
        # Check for New 3DS-specific title folders
        return None

    def validate_rom(self, rom_path: str, rom_type: str, is_rom_hack: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Validate ROM against 3DS capabilities.

        Args:
            rom_path: Relative ROM path
            rom_type: ROM type (NES, GB, GBA, SNES, etc.)
            is_rom_hack: Whether ROM is a hack

        Returns:
            (is_valid, error_message)
        """
        # Check if rom_type is supported on this hardware
        if rom_type not in self.supported_rom_types:
            hardware = self.device_config.get("hardware", "Unknown")
            return False, f"{rom_type} not supported on {hardware}"

        # Check forced inclusions/exclusions
        forced_inclusions = self.device_config.get("forcedInclusions", [])
        forced_exclusions = self.device_config.get("forcedExclusions", [])

        if rom_path in forced_exclusions:
            return False, "Forced exclusion in device config"

        if rom_path in forced_inclusions:
            return True, None

        return True, None

    def get_storage_info(self) -> Dict[str, Any]:
        """
        Get SD card storage information.

        Returns:
            Dict with storage stats and thresholds.
        """
        try:
            # Get filesystem stats for mount point
            stat = self.mount_point.stat()
            total = stat.st_blocks * stat.st_blksize if hasattr(stat, "st_blocks") else 0
            # TODO: Properly calculate used/free from statvfs

            return {
                "total_bytes": total,
                "used_bytes": 0,  # TODO: Calculate
                "free_bytes": 0,  # TODO: Calculate
                "warning_percent": self.device_config.get("storageThresholds", {}).get("warningPercent", 80),
                "abort_percent": self.device_config.get("storageThresholds", {}).get("abortPercent", 90),
            }
        except Exception as e:
            logger.error(f"Failed to get storage info: {e}")
            return {
                "total_bytes": 0,
                "used_bytes": 0,
                "free_bytes": 0,
                "warning_percent": 80,
                "abort_percent": 90,
            }

    def sync_roms(self, roms: List[Dict[str, Any]], dry_run: bool = True) -> Dict[str, Any]:
        """
        Sync ROMs to 3DS SD card.

        Args:
            roms: List of ROM configs
            dry_run: If True, only show what would be synced

        Returns:
            Sync results dict.
        """
        logger.info(f"Syncing {len(roms)} ROMs to {self.device_name} (dry_run={dry_run})")

        results = {"synced": 0, "skipped": 0, "failed": 0, "details": []}

        for rom in roms:
            rom_path = rom.get("path")
            rom_type = rom.get("architecture", "unknown")

            # Validate ROM
            is_valid, error = self.validate_rom(rom_path, rom_type, rom.get("isRomHack", False))

            if not is_valid:
                logger.warning(f"Skipping {rom_path}: {error}")
                results["skipped"] += 1
                results["details"].append({"rom": rom_path, "status": "skipped", "reason": error})
                continue

            # TODO: Actually sync ROM file
            if not dry_run:
                logger.info(f"Would copy {rom_path} to device")
                results["synced"] += 1
            else:
                logger.info(f"[DRY-RUN] Would copy {rom_path}")

            results["details"].append({"rom": rom_path, "status": "synced"})

        return results

    def sync_save_files(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Sync save files to/from device.

        Args:
            dry_run: If True, only show what would be synced

        Returns:
            Sync results dict.
        """
        logger.info(f"Syncing save files (dry_run={dry_run})")
        # TODO: Implement save file sync
        return {"synced": 0, "failed": 0, "details": []}

    def push_assets(self, asset_map: Dict[str, Dict[str, str]], dry_run: bool = True) -> Dict[str, Any]:
        """
        Push icons and banners to 3DS.

        3DS uses icons in specific locations depending on emulator.

        Asset resolution chain:
        1. Try GameTDB (if API key configured)
        2. Fall back to DuckDuckGo image search
        3. Skip if neither succeeds

        Args:
            asset_map: Mapping of ROM paths to asset info
            dry_run: If True, only show what would be pushed

        Returns:
            Push results dict.
        """
        logger.info(f"Pushing assets for {len(asset_map)} ROMs (dry_run={dry_run})")

        # Import asset handlers
        from vapor.assets.twilight import TwiLightAssetHandler
        from vapor.assets.gametdb import GameTDBHandler
        try:
            from vapor.assets.search import ddg_image_search, download_image
        except Exception:
            ddg_image_search = None
            download_image = None

        # Read GameTDB API key from config if available
        gametdb_key = self.device_config.get("assets", {}).get("gametdbApiKey")
        gametdb_handler = GameTDBHandler(api_key=gametdb_key) if gametdb_key else None

        twilight_handler = TwiLightAssetHandler(
            cache_dir=Path.home() / ".config" / "vapor-rom-mgr" / "twilight_assets"
        )

        results = {"pushed": 0, "skipped": 0, "failed": 0, "details": []}

        # For each ROM in asset_map, try to fetch/generate icon, then push to device
        for rom_path, assets in asset_map.items():
            rom_basename = os.path.basename(rom_path)
            icon_path = None

            # Try to find cached icon first
            icon_bytes = twilight_handler.fetch_icon(rom_basename)
            if icon_bytes:
                asset_dir = twilight_handler.cache_dir / os.path.splitext(rom_basename)[0]
                asset_dir.mkdir(parents=True, exist_ok=True)
                icon_path = asset_dir / f"{rom_basename}.png"
                if not icon_path.exists():
                    icon_path.write_bytes(icon_bytes)
                logger.info(f"Using cached icon for {rom_basename}")
            else:
                # Try GameTDB if available
                if gametdb_handler and gametdb_handler.enabled:
                    cover_bytes = gametdb_handler.fetch_cover_art(rom_basename, platform="GBA")
                    if cover_bytes:
                        asset_dir = twilight_handler.cache_dir / os.path.splitext(rom_basename)[0]
                        asset_dir.mkdir(parents=True, exist_ok=True)
                        icon_path = asset_dir / f"{rom_basename}.png"
                        icon_path.write_bytes(cover_bytes)
                        logger.info(f"Fetched cover art for {rom_basename} from GameTDB")
                    else:
                        logger.debug(f"No cover art from GameTDB for {rom_basename}")

                # Fallback to DuckDuckGo image search if still no icon
                if not icon_path and ddg_image_search and download_image:
                    query = f"{os.path.splitext(rom_basename)[0]} box art"
                    urls = ddg_image_search(query, max_results=1)
                    if urls:
                        tmpdir = twilight_handler.cache_dir / os.path.splitext(rom_basename)[0]
                        tmpdir.mkdir(parents=True, exist_ok=True)
                        candidate = tmpdir / "candidate1.img"
                        ok = download_image(urls[0], str(candidate))
                        if ok:
                            try:
                                generated = twilight_handler.generate_twilight_icon(
                                    str(candidate), str(tmpdir / f"{rom_basename}.png")
                                )
                                icon_path = Path(generated)
                                logger.info(f"Generated icon for {rom_basename} from web candidate")
                            except Exception as e:
                                logger.warning(f"Failed to generate twilight icon for {rom_basename}: {e}")

            if not icon_path or not icon_path.exists():
                results["skipped"] += 1
                results["details"].append(
                    {"rom": rom_path, "status": "skipped", "reason": "no icon available"}
                )
                continue

            # Push to device file system (SD-based path expected)
            device_mount = str(self.mount_point)
            device_rom_path = self.rom_path
            pushed = twilight_handler.push_to_sd(
                device_mount,
                device_rom_path,
                os.path.splitext(rom_basename)[0],
                str(icon_path),
                dry_run=dry_run,
            )
            if pushed:
                results["pushed"] += 1
                results["details"].append({"rom": rom_path, "status": "pushed", "asset": str(icon_path)})
            else:
                results["failed"] += 1
                results["details"].append({"rom": rom_path, "status": "failed", "asset": str(icon_path)})

        return results
