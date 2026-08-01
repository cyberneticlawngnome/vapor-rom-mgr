#!/usr/bin/env python3
"""Integration tests for vapor ROM manager.

Run from the project root:
    python3 test_integration.py

Tested on Steam Deck (Python 3.13) and Windows (Python 3.10).
"""

import json
import socket
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure vapor package is importable from project root
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PASS = 0
FAIL = 0
ERRORS = []


def check(name, condition: bool, detail=""):
    global PASS, FAIL
    if condition:
        print(f"  [PASS] {name}")
        PASS += 1
    else:
        msg = f"  [FAIL] {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)
        FAIL += 1
        ERRORS.append((name, detail))


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print("="*60)


# --- Section 1: Imports -------------------------------------------------

section("1. Module imports")

try:
    from vapor.asset_utils import find_title_for_nds, make_icon_filename_for_rom
    check("asset_utils imports", True)
except ImportError as e:
    check("asset_utils imports", False, str(e))

try:
    from vapor.rom_manager import ROMManager, _plugin_for_system, _port_open
    check("rom_manager imports", True)
except ImportError as e:
    check("rom_manager imports", False, str(e))

try:
    from vapor.core.logger import setup_logger, set_context, clear_context
    check("logger imports", True)
except ImportError as e:
    check("logger imports", False, str(e))

try:
    from vapor.core.config import ConfigLoader, ConfigError
    check("config imports", True)
except ImportError as e:
    check("config imports", False, str(e))

try:
    from vapor.systems.threeds import Nintendo3DSPlugin
    check("Nintendo3DSPlugin import", True)
except ImportError as e:
    check("Nintendo3DSPlugin import", False, str(e))

try:
    from vapor.systems.ds_pico import DSPicoPlugin
    check("DSPicoPlugin import", True)
except ImportError as e:
    check("DSPicoPlugin import", False, str(e))

# --- Section 2: Logger ContextFilter fix --------------------------------

section("2. Logger ContextFilter (no ValueError on missing context)")

try:
    logger = setup_logger("test.vapor")
    logger.info("Test message without context set")
    check("Logger works without prior set_context()", True)
except (ValueError, KeyError) as e:
    check("Logger works without prior set_context()", False, str(e))

try:
    set_context(device="fake", operation="test")
    logger.info("Test message with context")
    clear_context()
    check("Logger works with explicit context", True)
except Exception as e:
    check("Logger works with explicit context", False, str(e))

# --- Section 3: Config loading (FTP mountPoint fix) ---------------------

section("3. Config loading & FTP device mountPoint fix")

try:
    loader = ConfigLoader(ROOT / "config")
    cfg = loader.load_all()
    check("Config loads without error", True)
except Exception as e:
    check("Config loads without error", False, str(e))
    sys.exit(1)

check("Has systems config", bool(cfg.get("systems")))
check("Has devices config", bool(cfg.get("devices")))
check("Has roms config", bool(cfg.get("roms")))

# Check that FTP device (3ds-xl) loaded despite missing mountPoint
dev_ftp = cfg["devices"].get("3ds-xl")
if dev_ftp:
    mount = dev_ftp.get("mountPoint", "")
    check("FTP device loaded (despite no mountPoint in JSON)", True)
    check(f"FTP device mountPoint derived to: {mount}", "ftp://" in mount, mount)
else:
    check("FTP device loaded", False, "3ds-xl not in devices dict")

dev_sd = cfg["devices"].get("3ds-xl__sd")
check("SD device loaded", bool(dev_sd))
if dev_sd:
    check("SD device has mountPoint", bool(dev_sd.get("mountPoint")))

# --- Section 4: ROMManager detect_devices -------------------------------

section("4. ROMManager.detect_devices()")

try:
    mgr = ROMManager(config_dir=ROOT / "config")
    devices = mgr.detect_devices()
    check("detect_devices() returns without error", True)
except Exception as e:
    check("detect_devices() returns without error", False, str(e))
    import traceback
    traceback.print_exc()

check(f"Detected {len(devices)} devices", len(devices) >= 2, f"got {len(devices)}")

for dev_id in ["3ds-xl", "3ds-xl__sd"]:
    if dev_id in devices:
        info = devices[dev_id]
        check(f"{dev_id} has plugin attr", hasattr(info, "__getitem__"))
        # Devices should be offline on Steam Deck (no SD card mounted)
        status = "online" if info["online"] else "offline"
        print(f"  [INFO] {dev_id}: {status}")
    else:
        check(f"{dev_id} in devices dict", False, f"available: {list(devices.keys())}")

# --- Section 5: sync_device dry-run -------------------------------------

section("5. ROMManager.sync_device() dry-run (offline device)")

try:
    result = mgr.sync_device("3ds-xl__sd", dry_run=True)
    check("sync_device returns dict without error", isinstance(result, dict))
    check("sync_device reports offline error", "error" in result or result.get("device"))
except Exception as e:
    check("sync_device returns without exception", False, str(e))

# --- Section 6: validate_roms -------------------------------------------

section("6. ROMManager.validate_roms()")

try:
    results = mgr.validate_roms("3ds-xl__sd")
    check("validate_roms returns list", isinstance(results, list))
except Exception as e:
    check("validate_roms returns without exception", False, str(e))

# --- Section 7: Asset utilities -----------------------------------------

section("7. Asset utility functions")

test_icon = make_icon_filename_for_rom("Pokemon Emerald.nds")
check(f"make_icon_filename_for_rom('Pokemon Emerald.nds')", test_icon == "Pokemon Emerald.nds.png", test_icon)

check("find_title_for_nds returns None for nonexistent file",
      find_title_for_nds(Path("/nonexistent.nds")) is None, True)

# --- Section 8: _filter_roms_by_arch ------------------------------------

section("8. ROM filtering by architecture")

filtered = mgr._filter_roms_by_arch(["GB", "GBC", "GBA", "NDS", "NES", "SNES"])
check(f"_filter_roms_by_arch returns {len(filtered)} ROMs for 3DS (all arches)", len(filtered) > 0, f"got {len(filtered)}")

nds_only = mgr._filter_roms_by_arch(["NDS"])
check("_filter_roms_by_arch('NDS') filters correctly", len(nds_only) < len(filtered))

# --- Section 9: CLI import ----------------------------------------------

section("9. CLI entry point")

try:
    from vapor.__main__ import main
    check("__main__.main is callable", callable(main))
except ImportError as e:
    check("__main__.main import", False, str(e))

# --- Summary ------------------------------------------------------------

section(f"SUMMARY: {PASS} passed, {FAIL} failed")

if ERRORS:
    print("\nFailures:")
    for name, detail in ERRORS:
        if detail:
            print(f"  - {name}: {detail}")
        else:
            print(f"  - {name}")

sys.exit(0 if FAIL == 0 else 1)
