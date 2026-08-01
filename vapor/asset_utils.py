"""Reusable asset scanning utilities for the vapor ROM manager.

Extracted from standalone assets-scan.py so sync_device can call
into the same logic that powers --scan-assets."""

from pathlib import Path
from typing import Dict, Any, List, Optional

from vapor.core.logger import setup_logger

logger = setup_logger(__name__)


def find_title_for_nds(rom_path: Path) -> Optional[str]:
    """Try ndspy to read NDS game title; return None on any error."""
    try:
        from ndspy.ndspy import NDS  # noqa: F811
    except Exception:
        return None

    try:
        with open(rom_path, "rb") as f:
            nds = NDS(f.read())
        try:
            return nds.game_title
        except Exception:
            pass
    except Exception:
        pass
    return None


def make_icon_filename_for_rom(basename: str) -> str:
    """TwiLight naming convention: ``Game.nds`` -> ``Game.nds.png``."""
    return f"{basename}.png"


def build_asset_map(rom_config: Dict[str, Any],
                    mount_point: Path,
                    supported_arches: List[str],
                    twilight_handler) -> Dict[str, Dict[str, str]]:
    """Walk the ROM catalog and return an asset-map for every ROM that
    either has a cached icon or needs one.

    Returns ``{ rom_basename: {\"rom_path\": ..., \"icon_path\": ...} }`` where
    *``icon_path`` is ``None`` when no cached icon exists yet.*
    """
    asset_map = {}
    for rom_set in rom_config.get("romSets", []):
        arch = rom_set.get("architecture", "").lower()
        if arch not in [a.lower() for a in supported_arches]:
            continue

        for rom in rom_set.get("roms", []):
            basename = Path(rom.get("path")).name
            icon_bytes = twilight_handler.fetch_icon(basename) if twilight_handler else None
            asset_map[basename] = {
                "rom_path": rom.get("path"),
                "icon_path": str(icon_bytes.__class__) if icon_bytes else None,  # placeholder; push_assets resolves real path
                "has_cached_icon": bool(icon_bytes),
                "architecture": arch,
            }

    return asset_map


def set_psp_sort_mtimes(file_paths: List[Path]) -> None:
    """Set mtimes so PSP UI shows files in alphabetical order.

    PSP sorts by mtime descending, so the *last* alphabetical file gets
    00:00:00, each preceding file gets +1 second.
    """
    import os
    from datetime import datetime, timedelta

    sorted_paths = sorted(file_paths, key=lambda p: p.name.lower())
    base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for i in range(len(sorted_paths)):
        mtime = (base_time + timedelta(seconds=i)).timestamp()
        atime = mtime
        os.utime(sorted_paths[i], (atime, mtime))
