#!/usr/bin/env python3
"""
assets-scan.py

Standalone helper to scan configured mappings and generate candidate icons/banners for ROMs.
- Generates TwiLight Menu++ compatible 32x32 icons (quantized to <=15 colors, no semi-alpha)
- Downloads candidate images using DuckDuckGo image JSON endpoint as a fallback
- Saves candidates under ~/.config/deck-console-mgr/assets/<mapping-relative>/

Run in dry-run first. Use --apply to write generated icons to the assets directory.
"""

import os
import sys
import json
import argparse
import shutil
from urllib.parse import quote_plus

try:
    import requests
except Exception:
    requests = None

try:
    from PIL import Image
    from PIL import ImageOps
except Exception:
    Image = None

try:
    import ndspy
    from ndspy.ndspy import NDS
except Exception:
    ndspy = None

CONFIG_DIR = os.path.expanduser("~/.config/deck-console-mgr")
DEFAULT_CONFIG_PATH = os.path.join(CONFIG_DIR, "default.json")
ASSETS_DIR = os.path.join(CONFIG_DIR, "assets")

os.makedirs(ASSETS_DIR, exist_ok=True)

DEFAULT_CONFIG = {
    "mappings": [],
    "assets": {
        "candidate_count": 3,
        "twilight_icons_dir": "_nds/TWiLightMenu/icons",
        "allow_image_search_fallback": True,
        "auto_accept_top_image": False
    }
}


def load_default_config():
    cfg = DEFAULT_CONFIG.copy()
    try:
        if os.path.exists(DEFAULT_CONFIG_PATH):
            with open(DEFAULT_CONFIG_PATH, 'r') as f:
                on_disk = json.load(f)
                assets = on_disk.get('assets')
                if assets:
                    cfg_assets = cfg.get('assets', {}).copy()
                    cfg_assets.update(assets)
                    on_disk['assets'] = cfg_assets
                cfg.update(on_disk)
    except Exception as e:
        print(f"⚠️  Failed to load default config: {e}")
    return cfg


# ---- GBA checksum helper ----
def gba_update_header_checksum(rom_path):
    """Update the GBA header checksum at offset 0xBD based on bytes 0xA0..0xAC inclusive.
    Returns the new checksum byte value, or None on error."""
    try:
        with open(rom_path, 'r+b') as f:
            f.seek(0xA0)
            data = f.read(13)
            if len(data) != 13:
                print(f"⚠️  Unexpected header size reading logo bytes in {rom_path}")
                return None
            checksum = sum(data) & 0xFF
            f.seek(0xBD)
            f.write(bytes([checksum]))
            f.flush()
        return checksum
    except Exception as e:
        print(f"❌ Failed to update GBA header checksum for {rom_path}: {e}")
        return None


# ---- TwiLight icon generation ----

def remove_semi_alpha(img):
    """Convert semi-transparent pixels to either fully transparent or fully opaque by thresholding alpha."""
    if img.mode in ('RGBA', 'LA'):
        alpha = img.split()[-1]
        # threshold: alpha >= 128 -> 255, else -> 0
        alpha = alpha.point(lambda a: 255 if a >= 128 else 0)
        img.putalpha(alpha)
    return img


def quantize_to_palette(img, num_colors=15):
    # Convert to P mode with limited palette
    # Use median-cut quantization via .quantize
    q = img.convert('RGBA')
    # Remove semi-alpha first
    q = remove_semi_alpha(q)
    # Convert to P with k colors. PIL's quantize will include transparency as a color index.
    try:
        pal = q.convert('P', palette=Image.ADAPTIVE, colors=num_colors)
        # Ensure we keep full transparency as a single index when present
        return pal.convert('RGBA')
    except Exception:
        return q


def generate_twilight_icon(source_image_path, dest_path):
    """Generate a TwiLight-compatible 32x32 PNG icon from source image and write to dest_path."""
    if Image is None:
        raise RuntimeError('Pillow is required to generate icons')
    img = Image.open(source_image_path)
    # Ensure RGBA
    img = img.convert('RGBA')
    # Fit and crop to square then resize to 32x32
    img = ImageOps.fit(img, (32, 32), Image.LANCZOS)
    img = remove_semi_alpha(img)
    img = quantize_to_palette(img, num_colors=15)
    # Final save as PNG
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    img.save(dest_path, format='PNG')
    return dest_path


# ---- Image search / download (DuckDuckGo fallback) ----

def ddg_image_search(query, max_results=3):
    """Simple DuckDuckGo image JSON endpoint search. Returns list of dicts with 'image' key.
    This endpoint may be unofficial and ephemeral, but works as a pragmatic fallback."""
    results = []
    if requests is None:
        return results
    try:
        # First, get the token/params by requesting the main search page
        session = requests.Session()
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = session.get('https://duckduckgo.com/', headers=headers, timeout=10)
        # Query the i.js endpoint
        params = {'q': query}
        url = 'https://duckduckgo.com/i.js'
        while len(results) < max_results:
            r = session.get(url, params=params, headers=headers, timeout=10)
            if r.status_code != 200:
                break
            data = r.json()
            items = data.get('results') or data.get('items') or []
            for it in items:
                if 'image' in it:
                    results.append(it)
                    if len(results) >= max_results:
                        break
            # get next
            if 'next' in data and data['next']:
                url = data['next']
                params = {}
            else:
                break
    except Exception:
        pass
    return results[:max_results]


def download_image(url, dest_path, timeout=15):
    if requests is None:
        return False
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, stream=True, timeout=timeout)
        if r.status_code == 200:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, 'wb') as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
    except Exception:
        pass
    return False


# ---- Scanning and orchestration ----

def make_icon_filename_for_rom(basename):
    # basename here includes extension, e.g., 'Pokemon.nds' or 'Castlevania.gba'
    # TwiLight naming uses exact ROM filename plus .png -> Pokemon.nds.png
    return f"{basename}.png"


def find_title_for_nds(rom_path):
    if ndspy is None:
        return None
    try:
        with open(rom_path, 'rb') as f:
            nds = NDS(f.read())
            # ndspy's NDS.title property may exist; try reading banner title
            try:
                title = nds.game_title
            except Exception:
                # fallback: from the header
                title = None
            return title
    except Exception:
        return None


def scan_and_prepare_assets(cfg, apply=False, verbose=False):
    candidate_count = cfg.get('assets', {}).get('candidate_count', 3)
    allow_search = cfg.get('assets', {}).get('allow_image_search_fallback', True)
    auto_accept = cfg.get('assets', {}).get('auto_accept_top_image', False)

    mappings = cfg.get('mappings', [])
    summary = {'scanned': 0, 'missing_icon': 0, 'generated': 0}

    for local_dir, remote_dir in mappings:
        if not os.path.isdir(local_dir):
            if verbose:
                print(f"Skipping missing local mapping: {local_dir}")
            continue
        for root, _, files in os.walk(local_dir):
            rel_root = os.path.relpath(root, local_dir)
            rel_root = '' if rel_root == '.' else rel_root.replace('\\', '/')
            for fname in files:
                if not fname.lower().endswith(('.nds', '.gba')):
                    continue
                summary['scanned'] += 1
                rom_path = os.path.join(root, fname)
                basename = fname  # includes extension
                icon_name = make_icon_filename_for_rom(basename)
                # asset dir for this rom
                asset_relative_dir = os.path.join(rel_root, os.path.splitext(basename)[0])
                asset_store_dir = os.path.join(ASSETS_DIR, asset_relative_dir)
                os.makedirs(asset_store_dir, exist_ok=True)
                twilight_icon_path = os.path.join(asset_store_dir, icon_name)
                if os.path.exists(twilight_icon_path):
                    if verbose:
                        print(f"Icon already present for {fname} -> {twilight_icon_path}")
                    continue
                # missing icon
                summary['missing_icon'] += 1
                # Determine search query: try ndspy title for nds
                title = None
                if fname.lower().endswith('.nds'):
                    title = find_title_for_nds(rom_path)
                if not title:
                    # fallback: filename without extension
                    title = os.path.splitext(basename)[0]
                if verbose:
                    print(f"Missing icon for {basename}; using title='{title}' to search candidates")
                candidates = []
                # Try GameTDB if configured (not implemented here, placeholder)
                # Fallback to DuckDuckGo image search
                if allow_search and requests is not None:
                    q = f"{title} box art"
                    results = ddg_image_search(q, max_results=candidate_count)
                    for idx, r in enumerate(results):
                        img_url = r.get('image') or r.get('thumbnail') or r.get('url')
                        if not img_url:
                            continue
                        dest = os.path.join(asset_store_dir, f"candidate_{idx+1}.img")
                        ok = download_image(img_url, dest)
                        if ok:
                            candidates.append(dest)
                            if verbose:
                                print(f"Downloaded candidate {img_url} -> {dest}")

                # If we have candidates, generate twilight icons from top candidate(s)
                if candidates:
                    # generate icon from first candidate
                    try:
                        if apply or auto_accept:
                            gen_dest = os.path.join(asset_store_dir, icon_name)
                            generate_twilight_icon(candidates[0], gen_dest)
                            summary['generated'] += 1
                            print(f"Generated TwiLight icon for {basename}: {gen_dest}")
                        else:
                            print(f"Found {len(candidates)} candidate(s) for {basename} in {asset_store_dir}; run with --apply to generate icons")
                    except Exception as e:
                        print(f"❌ Failed to generate icon for {basename}: {e}")
                else:
                    print(f"No image candidates found for {basename}. Consider enabling GameTDB or providing images manually.")

    print("\nScan summary:")
    print(f"  scanned ROMs: {summary['scanned']}")
    print(f"  missing icons found: {summary['missing_icon']}")
    print(f"  icons generated: {summary['generated']}")
    return summary


# ---- CLI ----

def main():
    parser = argparse.ArgumentParser(description='Scan ROM mappings and prepare asset candidates/icons')
    parser.add_argument('--apply', action='store_true', help='Write generated icons to disk (otherwise dry-run)')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()

    cfg = load_default_config()
    if not cfg.get('mappings'):
        print('No mappings configured in default.json — nothing to scan.')
        sys.exit(1)

    summary = scan_and_prepare_assets(cfg, apply=args.apply, verbose=args.verbose)


if __name__ == '__main__':
    main()
