# Vapor ROM Manager

A multi-platform ROM and emulation stack manager for SteamDeck, 3DS, DS-Pico, and PSP.

## Overview

Vapor manages ROM collections, save files, and emulator assets across multiple gaming devices. It's designed to:

- **Centralize ROM configuration** in JSON/INI files (not hardcoded)
- **Auto-detect connected devices** via filesystem or network
- **Validate ROMs** against device capabilities (e.g., 3DS XL supports SNES, but original 3DS doesn't)
- **Manage save files** across devices
- **Handle device-specific assets** (icons, banners, cover art)
- **Support ROM hacks** with metadata tagging and manual asset overrides
- **Provide dry-run mode** for safe preview before syncing

## Current Features

### Supported Systems

- **Nintendo 3DS** (3DS, 3DS XL, New 3DS, New 3DS XL)
  - Detection via FTP (ftpd banner + SYST) or SD card (ID0 structure)
  - ROM type filtering by hardware capability
  - **Asset handlers**: GameTDB (primary, opt-in with API key) + DuckDuckGo fallback
  - **NDS banner support**: Read/write NDS banners via ndspy (optional)
- **DS-Pico Flash Cart**
  - Direct SD card mounting
  - DS-Lite and DS-i variant support
  - Storage threshold warnings (80% warning, 90% abort)
  - Asset ingestion from pre-populated SD cards
- **PSP** (planned)
  - FTP and SD card support
  - Older WiFi handling

### Configuration System

All configuration moved out of code into `config/` directory:

```
config/
├── systems.json                    # System definitions & capabilities
├── devices/                        # Per-device configs
│   ├── steamdeck-3ds-xl.json
│   └── ds-pico-001.json
└── roms/
    ├── default.json               # Default ROM set
    └── overrides/                 # ROM-specific metadata
        ├── pokemon-hacks.json
        └── series-assets.json
```

See [CONFIG.md](CONFIG.md) for complete schema documentation.

### Plugin Architecture

Systems are implemented as plugins:

- `vapor/systems/base.py` — Abstract `SystemPlugin` class
- `vapor/systems/threeds.py` — Nintendo 3DS implementation
- `vapor/systems/ds_pico.py` — DS-Pico implementation
- `vapor/systems/psp.py` — (Planned) PSP implementation

Assets are handled via pluggable handlers:

- `vapor/assets/base.py` — Abstract `AssetHandler` class
- `vapor/assets/gametdb.py` — **NEW**: GameTDB metadata & cover art (opt-in with API key)
- `vapor/assets/ndspy_banner.py` — **NEW**: NDS banner read/write (safe, with round-trip tests)
- `vapor/assets/picocover.py` — (Planned) PicoCover integration
- `vapor/assets/local.py` — Local filesystem assets

### Device Auto-Discovery

On startup, Vapor scans mount points and:

1. Detects known devices (3DS SD cards, DS-Pico, etc.)
2. Prompts user for new devices: "What is this device?"
3. Caches detection result in device config (`lastDetected` field)
4. Skips offline devices (unmounted SD cards) with a warning

### ROM Management

- **Capability Filtering**: ROMs unsupported by a device are automatically skipped
  - Example: SNES games won't sync to original 3DS
  - Use `forcedInclusions` / `forcedExclusions` per device to override

- **ROM Hack Support**: Tag hacks in metadata
  ```json
  {
    "path": "Pokemon/Pokemon Too Many Types.gba",
    "isRomHack": true,
    "displayName": "Pokemon: Too Many Types"
  }
  ```
  - Hacks skip PicoCover lookups (since they're not official)
  - Can have custom asset overrides in `roms/overrides/`

### Asset Management

- **Asset Resolution Chain** (for 3DS):
  1. Check local cache (TwiLight icons)
  2. **Try GameTDB** (if API key configured) → primary source
  3. **Fall back to DuckDuckGo** image search (if enabled)
  4. Skip if no icon available (logged)

- **GameTDB Integration**:
  - Reads API key from `config/devices/*.json` → `assets.gametdbApiKey` field
  - Completely opt-in: no key = no GameTDB calls
  - Includes retry logic (3 attempts) and timeout handling (10s)
  - Automatic caching of fetched covers

- **NDS Banner Support** (ndspy-based):
  - Safe read of NDS ROM banners
  - Safe write with automatic backup
  - Single-frame banner creation from images
  - Round-trip test support (read → modify → write)
  - Optional; requires `ndspy` in requirements.txt

- **DS-Pico Asset Ingestion**: Discover and cache pre-existing assets from DS card:
  ```bash
  vapor ingest-assets ds-pico-001
  ```

### Dry-Run & Logging

- **Dry-Run Mode**: Preview all operations without making changes
  ```bash
  vapor sync --dry-run
  ```

- **Structured Logging**: Device and operation context in all log output
  ```
  2026-07-25 12:34:56 | INFO     | steamdeck-3ds-xl | sync | Syncing 42 ROMs...
  ```

## Architecture

### Core Modules

- `vapor/core/config.py` — Configuration loading & validation
- `vapor/core/logger.py` — Centralized logging with context
- `vapor/rom_manager.py` — Main orchestrator

### System Plugins

Each plugin implements:

- `detect()` — Auto-detect device
- `validate_rom()` — Check ROM compatibility
- `get_storage_info()` — Free space & thresholds
- `sync_roms()` — Copy ROMs to device
- `sync_save_files()` — Backup/restore saves
- `push_assets()` — Upload icons, banners, etc.

### Asset Handlers

Each handler implements:

- `fetch_cover_art()` — Get cover image
- `fetch_banner()` — Get system-specific banner
- `fetch_icon()` — Get system-specific icon
- `supports_rom_hacks()` — Can find assets for hacks

## Installation

```bash
git clone https://github.com/cyberneticlawngnome/vapor-rom-mgr
cd vapor-rom-mgr
pip install -r requirements.txt
```

### Dependencies

- **requests** — HTTP client for asset fetching
- **Pillow** — Image processing (icon/banner generation)
- **ndspy** — NDS/DSi ROM parsing (optional, for banner support)
- **beautifulsoup4** — HTML parsing for web scraping

## Usage

### Initialize Configuration

```bash
python -m vapor init
```

This creates `config/` directory with example configs.

### Auto-Detect Devices

```bash
python -m vapor detect
```

Scans mount points and prompts for new devices.

### Dry-Run Sync

```bash
python -m vapor sync --dry-run
```

Preview what would be synced to all devices.

### Sync Specific Device

```bash
python -m vapor sync steamdeck-3ds-xl
```

### Ingest DS-Pico Assets

```bash
python -m vapor ingest-assets ds-pico-001
```

## Configuration Examples

### Minimal 3DS Setup

`config/devices/steamdeck-3ds-xl.json`:

```json
{
  "deviceId": "steamdeck-3ds-xl",
  "name": "SteamDeck 3DS XL",
  "system": "3DS",
  "hardware": "3DS-XL",
  "connectionMethod": "sd",
  "mountPoint": "/mnt/steamdeck/microsd",
  "romPath": "/ROMs",
  "storageThresholds": {
    "warningPercent": 80,
    "abortPercent": 90
  }
}
```

### 3DS with GameTDB Asset Handler

`config/devices/steamdeck-3ds-xl.json` (extended):

```json
{
  "deviceId": "steamdeck-3ds-xl",
  "name": "SteamDeck 3DS XL",
  "system": "3DS",
  "hardware": "3DS-XL",
  "connectionMethod": "sd",
  "mountPoint": "/mnt/steamdeck/microsd",
  "romPath": "/ROMs",
  "assets": {
    "gametdbApiKey": "YOUR_GAMETDB_API_KEY"
  },
  "storageThresholds": {
    "warningPercent": 80,
    "abortPercent": 90
  }
}
```

**Note**: GameTDB API keys are managed locally — never stored in the repo.

### DS-Pico with ROM Hacks

`config/devices/ds-pico-001.json`:

```json
{
  "deviceId": "ds-pico-001",
  "name": "DS-Pico (DS-i)",
  "system": "DS-Pico",
  "dsPicoHardware": "DS-i",
  "connectionMethod": "sd",
  "mountPoint": "/mnt/ds-pico-001",
  "romPath": "/roms",
  "forcedInclusions": ["Pokemon/Pokemon Unbound.gba"]
}
```

### ROM Config with Hacks

`config/roms/default.json`:

```json
{
  "romSets": [
    {
      "architecture": "gba",
      "roms": [
        {
          "path": "Pokemon/Pokemon Emerald.gba",
          "series": "Pokemon",
          "isRomHack": false
        },
        {
          "path": "Pokemon/Pokemon Unbound.gba",
          "series": "Pokemon",
          "isRomHack": true
        }
      ]
    }
  ]
}
```

## Testing

```bash
python -m pytest tests/
```

Run tests with verbose output:

```bash
python -m pytest tests/ -v
```

Tests include:
- `test_ndspy_banner.py` — NDS banner read/write/round-trip tests
- `test_gametdb.py` — GameTDB API handler tests (mocked)
- `test_threeds_assets.py` — 3DS asset integration tests

## Roadmap

- [ ] PSP support (FTP + SD fallback)
- [ ] PicoCover asset handler integration
- [ ] Save file sync (backup/restore)
- [ ] Web UI for configuration
- [ ] Multi-device batch operations
- [ ] ROM validation & checksums
- [ ] Homebrew detection & filtering
- [ ] NDS banner editor GUI (using ndspy)

## Contributing

Contributions welcome! Please:

1. Create a feature branch
2. Add tests for new functionality
3. Update documentation
4. Submit a pull request

## License

MIT

## References

- [CONFIG.md](CONFIG.md) — Configuration schema & examples
- [GameTDB](https://www.gametdb.com/) — Game metadata & cover art API
- [ndspy](https://github.com/RoadrunnerWMC/ndspy) — NDS file format parser
- [PicoCover](https://github.com/Scaletta/PicoCover) — DS game metadata
- [TWiLight Menu++](https://github.com/DS-Homebrew/TWiLightMenu) — 3DS/DS emulation hub
