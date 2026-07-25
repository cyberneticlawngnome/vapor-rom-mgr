Update: added assets-scan.py — standalone tool to detect missing NDS/GBA icons and download candidate images (DuckDuckGo fallback) and generate TwiLight-compatible 32x32 icons.

Usage:
  python3 assets-scan.py --verbose        # dry-run, list candidates
  python3 assets-scan.py --apply --verbose  # generate icons from top candidate and write to ~/.config/deck-console-mgr/assets/

Notes:
- Requires Pillow and requests for full functionality (they are optional but recommended).
- NDS title extraction via ndspy is optional — if ndspy present, the script will attempt to use NDS internal title for better search queries.
- This is a conservative first pass — I will integrate it into the main 3ds-sync flow and add GameTDB support and remote push in later commits.
