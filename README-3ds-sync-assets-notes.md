### Asset & metadata improvements

I added a requirements.txt that includes:
- requests
- Pillow
- ndspy
- beautifulsoup4

The main script now imports these optionally and implements helpers to:
- download candidate images for missing assets (image-search fallback)
- generate TwiLight Menu++ compatible 32x32 icons (quantized to <=15 colors, no semi-alpha)
- update the GBA header complement checksum (at 0xBD) after any binary modification; an external GBA embedding tool may be configured
- store candidate assets under ~/.config/deck-console-mgr/assets/ preserving mapping-relative paths

Notes:
- I intentionally imported external modules lazily and will print helpful diagnostics if they are missing at runtime.
- The actual NDS banner generation and embedding is left using ndspy where available; some higher-risk operations (GBA embedding) are gateable behind an external tool path in the config; the script will still update the GBA header checksum if you enable embedding and the external tool modifies the ROM.
- Next: integrate the detection/scan loop into the main processing pass so missing assets are discovered and optional downloads/pushes are executed under --apply and --confirm.
