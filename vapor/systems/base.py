"""
Base class for system plugins.

Each system (3DS, DS-Pico, PSP, etc.) is implemented as a plugin
deriving from this abstract base.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from vapor.core.logger import setup_logger

logger = setup_logger(__name__)


class SystemDetectionError(Exception):
    """Error during system detection."""
    pass


class SystemPlugin(ABC):
    """
    Abstract base class for system plugins.

    Each plugin is responsible for:
    - Detecting its hardware via filesystem or network
    - Validating ROMs against system capabilities
    - Managing ROM and save file syncing
    - Handling device-specific assets (icons, banners)
    """

    def __init__(self, device_config: Dict[str, Any]):
        """
        Initialize system plugin.

        Args:
            device_config: Device configuration dict (from devices/device-name.json)
        """
        self.device_config = device_config
        self.device_id = device_config.get("deviceId", "unknown")
        self.device_name = device_config.get("name", "Unknown Device")
        self.mount_point = Path(device_config.get("mountPoint", "/mnt"))
        self.rom_path = device_config.get("romPath", "/ROMs")
        self.save_file_path = device_config.get("saveFilePath")
        self.logger = setup_logger(f"vapor.systems.{self.__class__.__name__}")

    @property
    @abstractmethod
    def system_name(self) -> str:
        """Return the system name (e.g., '3DS', 'DS-Pico', 'PSP')."""
        pass

    @property
    @abstractmethod
    def supported_rom_types(self) -> List[str]:
        """Return list of supported ROM architecture types (e.g., ['NES', 'GB', 'GBA'])."""
        pass

    @abstractmethod
    def detect(self) -> bool:
        """
        Auto-detect if this device is connected and available.

        Returns:
            True if device detected and ready, False otherwise.

        Raises:
            SystemDetectionError: If detection fails unexpectedly.
        """
        pass

    @abstractmethod
    def validate_rom(self, rom_path: str, rom_type: str, is_rom_hack: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Validate whether a ROM can run on this device.

        Args:
            rom_path: Path to ROM file (relative to device romPath)
            rom_type: ROM architecture type (e.g., 'NES', 'GBA')
            is_rom_hack: Whether ROM is flagged as a hack

        Returns:
            Tuple of (is_valid, error_message).
            If valid, error_message is None.
            If invalid, error_message explains why.
        """
        pass

    @abstractmethod
    def get_storage_info(self) -> Dict[str, Any]:
        """
        Get storage information for the device.

        Returns:
            Dict with keys:
            - total_bytes: Total storage capacity
            - used_bytes: Used storage
            - free_bytes: Available storage
            - warning_percent: Configured warning threshold (default: 80)
            - abort_percent: Configured abort threshold (default: 90)
        """
        pass

    @abstractmethod
    def sync_roms(self, roms: List[Dict[str, Any]], dry_run: bool = True) -> Dict[str, Any]:
        """
        Sync ROM files to the device.

        Args:
            roms: List of ROM configs to sync (from roms/default.json and overrides)
            dry_run: If True, show what would be synced without actually syncing

        Returns:
            Dict with keys:
            - synced: Number of ROMs synced
            - skipped: Number of ROMs skipped (due to validation)
            - failed: Number of ROMs that failed to sync
            - details: List of detail dicts for each ROM operation
        """
        pass

    @abstractmethod
    def sync_save_files(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Sync save files (backups or restores).

        Args:
            dry_run: If True, show what would be synced without actually syncing

        Returns:
            Dict with keys:
            - synced: Number of saves synced
            - failed: Number of saves that failed
            - details: List of detail dicts
        """
        pass

    @abstractmethod
    def push_assets(self, asset_map: Dict[str, Dict[str, str]], dry_run: bool = True) -> Dict[str, Any]:
        """
        Push icons, banners, and other assets to the device.

        Asset formats are system-specific (e.g., DS-Pico needs specific banner formats).

        Args:
            asset_map: Dict mapping ROM paths to asset info:
                {"rom_path": {"icon": "/path/to/icon", "banner": "/path/to/banner", ...}}
            dry_run: If True, show what would be pushed without actually pushing

        Returns:
            Dict with keys:
            - pushed: Number of assets pushed
            - skipped: Number skipped (not needed or format invalid)
            - failed: Number that failed
            - details: List of detail dicts
        """
        pass

    def is_online(self) -> bool:
        """
        Check if device is currently online/accessible.

        Returns:
            True if device is reachable, False otherwise.
        """
        try:
            return self.detect()
        except SystemDetectionError:
            return False
