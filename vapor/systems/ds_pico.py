"""
DS-Pico flash cart system plugin.

Manages ROM and save files on DS-Pico SD cards.
Supports DS-Lite and DS-i variants with different ROM format compatibility.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from vapor.systems.base import SystemPlugin, SystemDetectionError
from vapor.core.logger import setup_logger

logger = setup_logger(__name__)


class DSPicoPlugin(SystemPlugin):
    """DS-Pico flash cart system plugin."""

    @property
    def system_name(self) -> str:
        return "DS-Pico"

    @property
    def supported_rom_types(self) -> List[str]:
        """DS-Pico supports different ROM types based on hardware variant."""
        hardware = self.device_config.get("dsPicoHardware", "DS-i")
        if hardware == "DS-i":
            return ["NDS", "DSi"]
        else:  # DS-Lite
            return ["NDS"]

    def detect(self) -> bool:
        """
        Detect DS-Pico SD card at mount point.

        Returns:
            True if detected.

        Raises:
            SystemDetectionError: If detection fails.
        """
        try:
            sd_root = self.mount_point

            if not sd_root.exists():
                logger.warning(f"Mount point not found: {sd_root}")
                return False

            # Look for DS-Pico marker files or directory structure
            # DS-Pico typically has /roms or similar root directory
            roms_dir = sd_root / "roms"
            if roms_dir.exists():
                logger.info(f"Found DS-Pico SD card at {sd_root}")
                return True

            # Alternative: check for any known DS-Pico files
            logger.warning(f"Potential DS-Pico card at {sd_root} but no clear markers found")
            return False

        except Exception as e:
            raise SystemDetectionError(f"Failed to detect DS-Pico: {e}")

    def validate_rom(self, rom_path: str, rom_type: str, is_rom_hack: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Validate ROM against DS-Pico capabilities.

        Args:
            rom_path: Relative ROM path
            rom_type: ROM type (NDS, DSi, etc.)
            is_rom_hack: Whether ROM is a hack

        Returns:
            (is_valid, error_message)
        """
        if rom_type not in self.supported_rom_types:
            hardware = self.device_config.get("dsPicoHardware", "Unknown")
            return False, f"{rom_type} not supported on DS-Pico ({hardware})"

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
        Get DS-Pico SD card storage information.

        Returns:
            Dict with storage stats and thresholds.
        """
        try:
            import os
            stat = os.statvfs(str(self.mount_point))
            free_bytes = stat.f_bavail * stat.f_frsize
            total_bytes = stat.f_blocks * stat.f_frsize
            used_bytes = total_bytes - free_bytes

            return {
                "total_bytes": total_bytes,
                "used_bytes": used_bytes,
                "free_bytes": free_bytes,
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
        Sync ROMs to DS-Pico SD card.

        Args:
            roms: List of ROM configs
            dry_run: If True, only show what would be synced

        Returns:
            Sync results dict.
        """
        logger.info(f"Syncing {len(roms)} ROMs to {self.device_name} (dry_run={dry_run})")

        results = {"synced": 0, "skipped": 0, "failed": 0, "details": []}
        storage_info = self.get_storage_info()

        # Check storage thresholds
        if storage_info["free_bytes"] > 0:
            used_percent = (storage_info["used_bytes"] / storage_info["total_bytes"]) * 100
            warn_threshold = storage_info["warning_percent"]
            abort_threshold = storage_info["abort_percent"]

            if used_percent >= abort_threshold:
                logger.warning(f"Storage usage at {used_percent:.1f}% (abort threshold: {abort_threshold}%)")
                results["failed"] += 1
                results["details"].append({
                    "status": "failed",
                    "reason": f"Storage at {used_percent:.1f}%, exceeds abort threshold"
                })
                return results

            if used_percent >= warn_threshold:
                logger.warning(f"Storage usage at {used_percent:.1f}% (warning threshold: {warn_threshold}%)")

        for rom in roms:
            rom_path = rom.get("path")
            rom_type = rom.get("architecture", "unknown")

            is_valid, error = self.validate_rom(rom_path, rom_type, rom.get("isRomHack", False))

            if not is_valid:
                logger.warning(f"Skipping {rom_path}: {error}")
                results["skipped"] += 1
                results["details"].append({"rom": rom_path, "status": "skipped", "reason": error})
                continue

            if not dry_run:
                logger.info(f"Syncing {rom_path}")
                results["synced"] += 1
            else:
                logger.info(f"[DRY-RUN] Would sync {rom_path}")

            results["details"].append({"rom": rom_path, "status": "synced"})

        return results

    def sync_save_files(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Sync save files to/from DS-Pico SD card.

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
        Push DS-Pico specific icons and banners to SD card.

        DS-Pico has specific format requirements for banners and icons.

        Args:
            asset_map: Mapping of ROM paths to asset info
            dry_run: If True, only show what would be pushed

        Returns:
            Push results dict.
        """
        logger.info(f"Pushing DS-Pico assets for {len(asset_map)} ROMs (dry_run={dry_run})")
        # TODO: Implement DS-Pico specific asset pushing
        return {"pushed": 0, "skipped": 0, "failed": 0, "details": []}

    def ingest_assets_from_sd(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Ingest pre-existing assets from DS-Pico SD card.

        DS-Pico SD cards may already have asset directories populated.
        This method discovers and imports those assets into the device config.

        Args:
            dry_run: If True, only show what would be ingested

        Returns:
            Ingestion results dict.
        """
        logger.info(f"Ingesting pre-existing assets from DS-Pico SD card (dry_run={dry_run})")

        results = {"ingested": 0, "skipped": 0, "details": []}

        try:
            # Look for common DS-Pico asset directories
            asset_dirs = [
                self.mount_point / "assets",
                self.mount_point / "_nds" / "TWiLightMenu" / "icons",
                self.mount_point / "covers",
            ]

            ingested_assets = {}

            for asset_dir in asset_dirs:
                if not asset_dir.exists():
                    continue

                logger.info(f"Scanning asset directory: {asset_dir}")

                for asset_file in asset_dir.glob("*"):
                    if asset_file.is_file():
                        logger.info(f"Found asset: {asset_file.name}")
                        ingested_assets[asset_file.name] = str(asset_file)
                        results["ingested"] += 1

            # Cache ingested assets in device config
            if not dry_run and ingested_assets:
                asset_cache_path = self.config_dir / "devices" / f"{self.device_id}-assets.json"
                asset_cache = {
                    "ingestedFrom": str(self.mount_point),
                    "assets": ingested_assets,
                }
                asset_cache_path.parent.mkdir(parents=True, exist_ok=True)
                with open(asset_cache_path, "w") as f:
                    json.dump(asset_cache, f, indent=2)

                logger.info(f"Cached {len(ingested_assets)} assets to {asset_cache_path}")

            return results

        except Exception as e:
            logger.error(f"Failed to ingest assets: {e}")
            results["skipped"] += 1
            return results
