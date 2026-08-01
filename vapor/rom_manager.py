"""Core ROM manager: orchestrates syncing, validation, and asset handling."""

import os
import shutil
import socket
from pathlib import Path
from typing import Dict, List, Any, Optional

from vapor.core.config import ConfigLoader
from vapor.core.logger import setup_logger, set_context, clear_context

logger = setup_logger(__name__)


def _plugin_for_system(system_name: str):
    """Return the SystemPlugin class for a given system name."""
    plugin_map = {
        "3DS": __import__("vapor.systems.threeds", fromlist=["Nintendo3DSPlugin"]).Nintendo3DSPlugin,
        "DS-Pico": __import__("vapor.systems.ds_pico", fromlist=["DSPicoPlugin"]).DSPicoPlugin,
    }
    cls = plugin_map.get(system_name)
    if not cls:
        raise ValueError(f"No plugin for system {system_name!r}")
    return cls


def _port_open(host: str, port: int, timeout: float = 3):
    """Quick TCP connect probe."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class ROMManager:
    """Orchestrates ROM management across multiple devices."""

    def __init__(self, config_dir: Path = None):
        self.config_dir = config_dir or Path("config")
        self.config_loader = ConfigLoader(self.config_dir)
        self.config = self.config_loader.load_all()
        self.devices: Dict[str, Any] = {}

    # -- Device detection ------------------------------------------------

    def detect_devices(self) -> Dict[str, Any]:
        """Scan for connected devices and populate ``self.devices``."""
        logger.info("Scanning for connected devices ...")
        self.devices.clear()

        for dev_id, dev_cfg in self.config["devices"].items():
            system = dev_cfg.get("system", "")
            conn_method = dev_cfg.get("connectionMethod", "sd")
            try:
                PluginCls = _plugin_for_system(system)
            except ValueError:
                logger.warning(f"No plugin for device {dev_id} (system={system})")
                continue

            plugin = PluginCls(dev_cfg)
            online = False

            if conn_method == "ftp":
                net = dev_cfg.get("network", {})
                host = net.get("host", "")
                port = net.get("port", 5000)
                online = _port_open(host, port) if host else False
            else:
                # SD card -- mount point must exist
                online = plugin.mount_point.exists() if isinstance(plugin.mount_point, Path) else os.path.isdir(str(plugin.mount_point))

            self.devices[dev_id] = {"plugin": plugin, "online": online}
            status = "online" if online else "offline"
            logger.info(f"  {dev_id} ({plugin.device_name}): {status}")

        return self.devices

    # -- Sync -----------------------------------------------------------

    def sync_device(self, device_id: str, dry_run: bool = True) -> Dict[str, Any]:
        """Sync ROMs and push missing assets to *device_id*.

        Steps
        ------
        1. Verify device is configured & online (detect if needed).
        2. Filter ROMs by supported architectures.
        3. Check storage thresholds.
        4. Copy ROM files (skip when identical on device).
        5. Scan for missing icons -> fetch via resolution chain -> push.
        """
        set_context(device=device_id, operation="sync")
        try:
            dev_cfg = self.config["devices"].get(device_id)
            if not dev_cfg:
                logger.error(f"Device {device_id} not found in config")
                return {"error": "Device not found"}

            # Ensure we have a plugin instance
            self.detect_devices()
            entry = self.devices.get(device_id)
            if not entry:
                return {"error": f"Plugin not loaded for {device_id}"}
            plugin = entry["plugin"]

            if not plugin.is_online():
                logger.warning(f"{device_id} is offline — aborting sync")
                return {"error": "Device offline"}

            dev_name = plugin.device_name
            logger.info(f"Syncing device: {dev_name} (dry_run={dry_run})")

            # 1\. Filter ROMs by supported arches (case-insensitive)
            sys_caps = self.config["systems"].get("systems", {}).get(
                dev_cfg.get("system", ""), {}
            )
            supported = [a.upper() for a in sys_caps.get("capabilities", [])]
            rom_list = self._filter_roms_by_arch(supported)
            logger.info(f"  {len(rom_list)} ROMs match capabilities")

            # 2\. Validate & copy ROMs
            sync_result = plugin.sync_roms(rom_list, dry_run=dry_run)

            # 3\. Push assets (icon resolution chain)
            asset_map = {}
            for rom in rom_list:
                basename = Path(rom.get("path", "")).name
                asset_map[basename] = {"architecture": rom.get("architecture")}

            asset_result = plugin.push_assets(asset_map, dry_run=dry_run)

            return {
                "device": device_id,
                "rom_sync": sync_result,
                "asset_push": asset_result,
            }
        finally:
            clear_context()

    # -- Validate -------------------------------------------------------

    def validate_roms(self, device_id: str) -> List[Dict[str, Any]]:
        """Validate all configured ROMs against a device's capabilities."""
        set_context(device=device_id, operation="validate")
        try:
            dev_cfg = self.config["devices"].get(device_id)
            if not dev_cfg:
                return [{"error": "Device not found"}]

            self.detect_devices()
            entry = self.devices.get(device_id)
            plugin = entry["plugin"] if entry else None

            if not plugin:
                return [{"error": "Plugin not loaded"}]

            sys_caps = self.config["systems"].get("systems", {}).get(
                dev_cfg.get("system", ""), {}
            )
            supported = [a.upper() for a in sys_caps.get("capabilities", [])]
            rom_list = self._filter_roms_by_arch(supported)

            results = []
            for rom in rom_list:
                is_valid, error = plugin.validate_rom(
                    rom.get("path"),
                    rom.get("architecture", "unknown"),
                    rom.get("isRomHack", False),
                )
                results.append({"rom": rom.get("path"), "valid": is_valid, "reason": error})

            return results
        finally:
            clear_context()

    # -- Asset scan (standalone command) --------------------------------

    def scan_assets(self, device_id: str, dry_run: bool = True) -> Dict[str, Any]:
        """Asset-only scan: discover missing icons and optionally push."""
        set_context(device=device_id, operation="scan_assets")
        try:
            dev_cfg = self.config["devices"].get(device_id)
            if not dev_cfg:
                return {"error": "Device not found"}

            self.detect_devices()
            entry = self.devices.get(device_id)
            plugin = entry["plugin"] if entry else None
            if not plugin:
                return {"error": "Plugin not loaded"}

            # Build asset map from ROM config
            sys_caps = self.config["systems"].get("systems", {}).get(
                dev_cfg.get("system", ""), {}
            )
            supported = [a.upper() for a in sys_caps.get("capabilities", [])]
            rom_list = self._filter_roms_by_arch(supported)

            asset_map = {}
            for rom in rom_list:
                basename = Path(rom.get("path", "")).name
                asset_map[basename] = {"architecture": rom.get("architecture")}

            result = plugin.push_assets(asset_map, dry_run=dry_run)
            return result
        finally:
            clear_context()

    # -- Internal helpers -----------------------------------------------

    def _filter_roms_by_arch(self, supported_upper: List[str]) -> List[Dict[str, Any]]:
        """Return flat list of ROM dicts whose architecture is in *supported_upper*."""
        roms = []
        rom_config = self.config.get("roms", {})
        for rom_set in rom_config.get("romSets", []):
            arch = rom_set.get("architecture", "").upper()
            if arch not in supported_upper:
                continue
            for rom in rom_set.get("roms", []):
                entry = dict(rom)
                entry["architecture"] = arch
                roms.append(entry)
        return roms

    def ingest_ds_pico_assets(self, device_id: str, sd_card_path: Path, dry_run: bool = True) -> Dict[str, Any]:
        """Ingest pre-existing assets from a DS-Pico SD card."""
        set_context(device=device_id, operation="ingest_assets")
        try:
            self.detect_devices()
            entry = self.devices.get(device_id)
            plugin = entry["plugin"] if entry else None

            if not plugin or not isinstance(plugin, __import__("vapor.systems.ds_pico", fromlist=["DSPicoPlugin"]).DSPicoPlugin):
                return {"error": "Not a DS-Pico device"}

            return plugin.ingest_assets_from_sd(dry_run=dry_run)
        finally:
            clear_context()
