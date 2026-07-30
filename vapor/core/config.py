"""
Configuration loading and validation for Vapor ROM Manager.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from vapor.core.logger import setup_logger

logger = setup_logger(__name__)


class ConfigError(Exception):
    """Configuration loading/validation error."""

    pass


class ConfigLoader:
    """Load and validate Vapor configuration files."""

    def __init__(self, config_dir: Path = None):
        """
        Initialize config loader.

        Args:
            config_dir: Root configuration directory (default: ./config)
        """
        self.config_dir = config_dir or Path("config")
        self.systems_config = None
        self.devices_configs = {}
        self.roms_config = None
        self.roms_overrides = {}

    def load_all(self) -> Dict[str, Any]:
        """Load all configuration files."""
        self.load_systems()
        self.load_devices()
        self.load_roms()
        self.load_rom_overrides()
        return {
            "systems": self.systems_config,
            "devices": self.devices_configs,
            "roms": self.roms_config,
            "overrides": self.roms_overrides,
        }

    def load_systems(self) -> Dict[str, Any]:
        """Load systems.json and validate."""
        path = self.config_dir / "systems.json"
        logger.info(f"Loading systems configuration from {path}")

        if not path.exists():
            raise ConfigError(f"systems.json not found at {path}")

        try:
            with open(path) as f:
                self.systems_config = json.load(f)

            # Validate required top-level key
            if "systems" not in self.systems_config:
                raise ConfigError("systems.json must contain 'systems' key")

            logger.info(f"Loaded {len(self.systems_config['systems'])} system definitions")
            return self.systems_config
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in systems.json: {e}")

    def load_devices(self) -> Dict[str, Dict[str, Any]]:
        """Load all device configurations from devices/ directory."""
        devices_dir = self.config_dir / "devices"
        logger.info(f"Loading device configurations from {devices_dir}")

        if not devices_dir.exists():
            logger.warning(f"devices directory not found at {devices_dir} — no devices configured")
            return {}

        for device_file in sorted(devices_dir.glob("*.json")):
            try:
                with open(device_file) as f:
                    device_config = json.load(f)

                device_id = device_config.get("deviceId") or device_file.stem
                self._validate_device_config(device_config)
                self.devices_configs[device_id] = device_config
                logger.info(f"Loaded device config: {device_id}")
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in {device_file.name}: {e}")
            except ConfigError as e:
                logger.warning(f"Invalid device config {device_file.name}: {e}")

        return self.devices_configs

    def load_roms(self) -> Dict[str, Any]:
        """Load default roms.json configuration."""
        path = self.config_dir / "roms" / "default.json"
        logger.info(f"Loading default ROM configuration from {path}")

        if not path.exists():
            logger.warning(f"default.json not found at {path} — no default ROMs configured")
            self.roms_config = {"romSets": []}
            return self.roms_config

        try:
            with open(path) as f:
                self.roms_config = json.load(f)

            if "romSets" not in self.roms_config:
                raise ConfigError("default.json must contain 'romSets' key")

            logger.info(f"Loaded {len(self.roms_config['romSets'])} ROM sets")
            return self.roms_config
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in default.json: {e}")

    def load_rom_overrides(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load ROM metadata overrides from overrides/ directory."""
        overrides_dir = self.config_dir / "roms" / "overrides"
        logger.info(f"Loading ROM overrides from {overrides_dir}")

        if not overrides_dir.exists():
            logger.info("No overrides directory found — no ROM overrides")
            return {}

        for override_file in sorted(overrides_dir.glob("*.json")):
            try:
                with open(override_file) as f:
                    override_data = json.load(f)

                override_key = override_file.stem
                self.roms_overrides[override_key] = override_data
                logger.info(f"Loaded ROM overrides: {override_key}")
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in {override_file.name}: {e}")

        return self.roms_overrides

    def _validate_device_config(self, config: Dict[str, Any]) -> None:
        """Validate device configuration structure."""
        required = ["name", "system", "connectionMethod", "mountPoint", "romPath"]
        missing = [key for key in required if key not in config]

        if missing:
            raise ConfigError(f"Missing required device config keys: {', '.join(missing)}")

        # Validate system exists in systems config
        if self.systems_config:
            system = config.get("system")
            if system not in self.systems_config.get("systems", {}):
                raise ConfigError(f"Unknown system: {system}")

    def get_device_by_id(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get device configuration by ID."""
        return self.devices_configs.get(device_id)

    def get_system_capabilities(self, system_name: str) -> Optional[Dict[str, Any]]:
        """Get system capabilities from systems.json."""
        if not self.systems_config:
            return None
        return self.systems_config.get("systems", {}).get(system_name)
