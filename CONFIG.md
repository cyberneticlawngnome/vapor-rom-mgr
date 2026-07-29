# Vapor ROM Manager - Configuration Schema

This document describes the configuration structure for vapor-rom-mgr.

## Directory Structure

```
config/
├── systems.json           # Global system capabilities & device profiles
├── devices/               # Per-device configurations
│   ├── steamdeck.json
│   ├── 3ds-xl.json
│   └── ds-pico-001.json
└── roms/
    ├── default.json       # Default ROM configuration
    └── overrides/         # ROM-specific metadata & asset overrides
        ├── pokemon-hacks.json
        └── series-assets.json
```

## systems.json

Defines system capabilities and device profiles. System detection logic uses this as the reference.

```json
{
  "systems": {
    "3DS": {
      "displayName": "Nintendo 3DS",
      "supportedRomTypes": ["NES", "GB", "GBC", "GBA"],
      "connectionMethods": ["ftp", "sd"],
      "detectionMethods": ["ftpd_banner", "id0_check"]
    },
    "3DS-XL": {
      "displayName": "Nintendo 3DS XL",
      "supportedRomTypes": ["NES", "GB", "GBC", "GBA", "SNES"],
      "connectionMethods": ["ftp", "sd"],
      "detectionMethods": ["ftpd_banner", "id0_check"]
    },
    "DS-Pico": {
      "displayName": "DS Pico Flash Cart",
      "supportedRomTypes": ["NDS"],
      "variants": {
        "DS-Lite": ["NDS"],
        "DS-i": ["NDS", "DSi"]
      },
      "connectionMethods": ["sd"],
      "detectionMethods": ["manual_prompt"]
    },
    "PSP": {
      "displayName": "PlayStation Portable",
      "supportedRomTypes": ["PSP"],
      "connectionMethods": ["ftp", "sd"],
      "detectionMethods": ["ftp_banner"]
    }
  }
}
```

## devices/device-name.json

Per-device configuration. Overrides system defaults.

```json
{
  "deviceId": "unique-device-identifier",
  "name": "SteamDeck",
  "system": "3DS",
  "hardware": "3DS-XL",
  "connectionMethod": "sd",
  "mountPoint": "/mnt/steamdeck/microsd",
  "romPath": "/games",
  "saveFilePath": "/games/saves",
  "storageThresholds": {
    "warningPercent": 80,
    "abortPercent": 90
  },
  "romConfig": "default.json",
  "forcedInclusions": [],
  "forcedExclusions": [],
  "dsPicoHardware": "DS-i",
  "dsPicoAssetCache": "config/devices/ds-pico-001-assets.json",
  "lastDetected": "2026-07-25T12:00:00Z"
}
```

### Device Config Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `deviceId` | string | Yes | Unique identifier for this device (UUID or path-safe name) |
| `name` | string | Yes | Human-readable device name |
| `system` | string | Yes | System type (3DS, DS-Pico, PSP, etc.) |
| `hardware` | string | No | Hardware variant (3DS, 3DS-XL, DS-Lite, DS-i) |
| `connectionMethod` | string | Yes | How to connect: `sd`, `ftp`, etc. |
| `mountPoint` | string | Yes (for SD) | Mount path on local filesystem |
| `romPath` | string | Yes | Path to ROM storage on device |
| `saveFilePath` | string | No | Path to save file storage |
| `storageThresholds` | object | No | Custom storage warning thresholds |
| `romConfig` | string | No | Which ROM config to use (default: `default.json`) |
| `forcedInclusions` | array | No | ROM files to always include, regardless of capability |
| `forcedExclusions` | array | No | ROM files to never include |
| `dsPicoHardware` | string | No (for DS-Pico) | `DS-Lite` or `DS-i` |
| `dsPicoAssetCache` | string | No (for DS-Pico) | Path to cached DS-Pico asset metadata |
| `lastDetected` | string | No | ISO 8601 timestamp of last auto-detection |

## roms/default.json

Default ROM configuration. Per-device configs can override or extend this.

```json
{
  "romSets": [
    {
      "architecture": "gb",
      "displayName": "Game Boy",
      "extensions": [".gb", ".gbc"],
      "roms": [
        {
          "path": "Pokemon/Pokemon Red.gb",
          "series": "Pokemon",
          "isRomHack": false,
          "tags": []
        },
        {
          "path": "Zelda/Link's Awakening.gb",
          "series": "Zelda",
          "isRomHack": false,
          "tags": []
        }
      ]
    },
    {
      "architecture": "gba",
      "displayName": "Game Boy Advance",
      "extensions": [".gba", ".agb"],
      "roms": [
        {
          "path": "Pokemon/Pokemon Emerald.gba",
          "series": "Pokemon",
          "isRomHack": false,
          "tags": []
        }
      ]
    }
  ]
}
```

### ROM Entry Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | Yes | Path relative to `romPath` |
| `series` | string | Yes | Series name (Pokemon, Zelda, etc.) |
| `isRomHack` | boolean | No | Whether this is a ROM hack (skips PicoCover lookup) |
| `tags` | array | No | Custom tags for filtering/organization |

## roms/overrides/pokemon-hacks.json

ROM-specific metadata and asset overrides.

```json
{
  "overrides": [
    {
      "romPath": "Pokemon/Pokemon Too Many Types.gba",
      "series": "Pokemon",
      "isRomHack": true,
      "displayName": "Pokemon: Too Many Types",
      "coverArt": "assets/pokemon-tmt-cover.png",
      "banner": "assets/pokemon-tmt-banner.bin",
      "icon": "assets/pokemon-tmt-icon.bmp",
      "tags": ["hack", "expanded-types"]
    },
    {
      "romPath": "Pokemon/Pokemon Unbound.gba",
      "series": "Pokemon",
      "isRomHack": true,
      "displayName": "Pokemon Unbound",
      "coverArt": "assets/pokemon-unbound-cover.png",
      "banner": "assets/pokemon-unbound-banner.bin",
      "icon": "assets/pokemon-unbound-icon.bmp",
      "tags": ["hack", "postgame"]
    }
  ]
}
```

## roms/overrides/series-assets.json

Per-series asset fallbacks (used when PicoCover fails or no specific override exists).

```json
{
  "seriesAssets": {
    "Pokemon": {
      "coverArt": "assets/series/pokemon-cover.png",
      "banner": "assets/series/pokemon-banner.bin",
      "icon": "assets/series/pokemon-icon.bmp"
    },
    "Zelda": {
      "coverArt": "assets/series/zelda-cover.png",
      "banner": "assets/series/zelda-banner.bin",
      "icon": "assets/series/zelda-icon.bmp"
    }
  }
}
```

## devices/ds-pico-001-assets.json

Cached asset metadata ingested from DS-Pico SD card. This is auto-generated during initial setup.

```json
{
  "ingestedFrom": "/mnt/ds-pico-001/assets",
  "ingestedAt": "2026-07-25T12:00:00Z",
  "assets": [
    {
      "romPath": "Pokemon Red.nds",
      "banner": "assets/pokemon-red-banner.bin",
      "icon": "assets/pokemon-red-icon.bmp",
      "coverArt": "assets/pokemon-red-cover.png"
    }
  ]
}
```

## Configuration Resolution Order

When determining config for a ROM operation:

1. **Device-specific forced inclusions/exclusions** (highest priority)
2. **ROM-specific metadata overrides** (roms/overrides/)
3. **Series-level assets** (roms/overrides/series-assets.json)
4. **PicoCover lookup** (if ROM is not tagged as hack)
5. **Device ROM config** (devices/{device}.json's romConfig reference)
6. **Default ROM config** (roms/default.json)
7. **System capabilities** (systems.json)
8. **Generic fallback assets** (lowest priority)

## Device Auto-Discovery

On startup, the tool scans mount points (configurable) and:

1. Looks for known device markers (e.g., `Nintendo 3DS/` folder, DS-Pico root marker)
2. If a new device is detected, prompts user:
   - "Found new device at `/mnt/my-device/`. What is it? (3DS / 3DS-XL / DS-Pico / PSP / Other)"
   - For DS-Pico: "What hardware variant? (DS-Lite / DS-i)"
   - Creates a device config file and caches the choice

3. If a known device is not found, marks it as offline
4. If a device config file exists but device is not detected, warns but continues (device may be unmounted)

## Example: Full Setup

```
config/
├── systems.json
├── devices/
│   ├── steamdeck-3ds-xl.json
│   └── ds-pico-001.json
└── roms/
    ├── default.json
    └── overrides/
        ├── pokemon-hacks.json
        └── series-assets.json
```

User runs: `vapor-rom-mgr sync`

1. Scans mount points, detects `/mnt/steamdeck/microsd` (known 3DS XL) and `/mnt/ds-pico-001` (new DS-Pico)
2. Prompts: "Detected new device at `/mnt/ds-pico-001`. What hardware? (DS-Lite / DS-i)"
3. User selects "DS-i"
4. Creates `config/devices/ds-pico-001.json` with `hardware: "DS-i"`
5. For SteamDeck: loads `config/devices/steamdeck-3ds-xl.json`, applies `config/roms/default.json`
6. For DS-Pico: loads `config/devices/ds-pico-001.json`, applies `config/roms/default.json`, filters by DS-i capabilities
7. Runs dry-run first (shows what would sync), then syncs on user confirmation

