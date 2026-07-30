#!/usr/bin/env python3
import os
import sys
import time
import argparse
import hashlib
import ftplib
import socket
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import json

# Optional dependencies (imported lazily)
try:
    import requests
except Exception:
    requests = None

try:
    from PIL import Image
except Exception:
    Image = None

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

try:
    import ndspy
    from ndspy.ndspy import NDS
except Exception:
    ndspy = None

# --- CONFIGURATION DEFAULTS ---
DEFAULT_CONFIG = {
    "scan_ip_start": "10.0.0.100",
    "scan_ip_end": "10.0.0.129",
    "ftp_port": 5000,
    "timeout": 3,
    "mappings": [
        ["/run/media/SN01T/emudeck/Emulation/roms/gb", "/ROMs/gb"],
        ["/run/media/SN01T/emudeck/Emulation/roms/nes", "/ROMs/nes"]
    ],
    "aliases": {
        "Pokemon_Emerald_Patched.gba": "Pokemon - Emerald Version (USA).gba",
        "Pokemon_Emerald_Patched.sav": "Pokemon - Emerald Version (USA).sav"
    },
    "valid_extensions": [".gba", ".nds", ".sav", ".gb", ".gbc", ".cia"],
    "confirm_on_conflict": True,
    "bulk_override_policy": "prompt",  # prompt | source_wins | destination_wins
    # Asset management defaults
    "assets": {
        "candidate_count": 3,
        "twilight_icons_dir": "_nds/TWiLightMenu/icons",
        "emudeck_assets_dir": "",  # leave empty to mirror sidecars
        "enable_gametdb": False,
        "gametdb_key": "",
        "allow_image_search_fallback": True,
        "auto_accept_top_image": False
    },
    "gba_embed_tool": ""  # Optional external tool path for GBA embedding (if empty, embedding disabled)
}

# Paths for configuration and state
CONFIG_DIR = os.path.expanduser("~/.config/deck-console-mgr")
DEFAULT_CONFIG_PATH = os.path.join(CONFIG_DIR, "default.json")
DEVICES_DIR = os.path.join(CONFIG_DIR, "devices")
DB_PATH = os.path.join(CONFIG_DIR, "3ds_sync_db.json")
BACKUP_DIR = os.path.join(CONFIG_DIR, "backups")
CLOUD_SAVE_DIR = os.path.join(CONFIG_DIR, "cloud_saves")
ASSETS_DIR = os.path.join(CONFIG_DIR, "assets")

os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(DEVICES_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(CLOUD_SAVE_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)


# --- UTILITY: Config & State ---
def load_default_config():
    cfg = DEFAULT_CONFIG.copy()
    try:
        if os.path.exists(DEFAULT_CONFIG_PATH):
            with open(DEFAULT_CONFIG_PATH, 'r') as f:
                on_disk = json.load(f)
                # merge assets sub-dict carefully
                assets = on_disk.get('assets')
                if assets:
                    cfg_assets = cfg.get('assets', {}).copy()
                    cfg_assets.update(assets)
                    on_disk['assets'] = cfg_assets
                cfg.update(on_disk)
    except Exception:
        pass
    return cfg


# (existing functions unchanged...) Removed here for brevity but retained in file
