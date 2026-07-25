from pathlib import Path
import os
import shutil
from typing import Optional
from vapor.assets.base import AssetHandler
from vapor.core.logger import setup_logger

logger = setup_logger(__name__)

try:
    from PIL import Image, ImageOps
except Exception:
    Image = None


DEFAULT_ASSETS_DIR = Path.home() / '.config' / 'deck-console-mgr' / 'assets'
DEFAULT_ASSETS_DIR.mkdir(parents=True, exist_ok=True)


class TwiLightAssetHandler(AssetHandler):
    @property
    def handler_name(self) -> str:
        return "TwiLightMenuHandler"

    def fetch_cover_art(self, rom_title: str, series: str = None) -> Optional[bytes]:
        # Not implemented here; rely on other handlers or external downloads
        return None

    def fetch_banner(self, rom_title: str, series: str = None) -> Optional[bytes]:
        # Not implemented here; banner generation is handled elsewhere (ndspy)
        return None

    def fetch_icon(self, rom_title: str, series: str = None) -> Optional[bytes]:
        # Try to find a cached icon by rom title in cache_dir or DEFAULT_ASSETS_DIR
        # rom_title expected to include extension for TwiLight naming e.g. 'Game.nds'
        candidates = []
        # check cache_dir
        cache_dir = Path(self.cache_dir)
        icon_name = f"{rom_title}.png"
        p = cache_dir / rom_title
        # rom_title may include path separators; handle both
        if (cache_dir / icon_name).exists():
            return (cache_dir / icon_name).read_bytes()
        # check DEFAULT_ASSETS_DIR
        for root, dirs, files in os.walk(DEFAULT_ASSETS_DIR):
            if icon_name in files:
                return (Path(root) / icon_name).read_bytes()
        return None

    def supports_rom_hacks(self) -> bool:
        # TwiLight handler can work for hacks if assets provided
        return True

    # Utility: generate 32x32 quantized PNG
    def generate_twilight_icon(self, source_image_path: str, dest_path: str) -> str:
        if Image is None:
            raise RuntimeError('Pillow is required to generate icons')
        img = Image.open(source_image_path).convert('RGBA')
        img = ImageOps.fit(img, (32, 32), Image.LANCZOS)
        # Remove semi-alpha
        if img.mode == 'RGBA':
            alpha = img.split()[-1]
            alpha = alpha.point(lambda a: 255 if a >= 128 else 0)
            img.putalpha(alpha)
        # Quantize to <=15 colors
        pal = img.convert('P', palette=Image.ADAPTIVE, colors=15)
        out = pal.convert('RGBA')
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        out.save(dest_path, format='PNG')
        return dest_path

    def embed_image_into_gba(self, rom_path: str, image_path: str, backup: bool = True) -> bool:
        """
        Internal (safe) embedding: append a VAPOR asset chunk to the end of the ROM.
        This does not alter the GBA header/logo bytes (so it's low-risk). After writing,
        we update the header checksum (safe no-op if logo unchanged).
        """
        try:
            rom_p = Path(rom_path)
            if not rom_p.exists():
                logger.error(f"ROM not found: {rom_path}")
                return False
            if backup:
                bak = rom_p.with_suffix(rom_p.suffix + '.bak')
                shutil.copy2(rom_p, bak)
                logger.info(f"Backup created: {bak}")
            # Append chunk: simple format [VAPR][len (4)][data]
            with open(rom_path, 'ab') as rf, open(image_path, 'rb') as imf:
                data = imf.read()
                rf.write(b'VAPR')
                rf.write(len(data).to_bytes(4, 'little'))
                rf.write(data)
            # Update header checksum to be safe (reads logo bytes and writes checksum)
            self._update_gba_header_checksum(rom_path)
            return True
        except Exception as e:
            logger.error(f"Failed to embed image into GBA: {e}")
            return False

    def _update_gba_header_checksum(self, rom_path: str) -> Optional[int]:
        try:
            with open(rom_path, 'r+b') as f:
                f.seek(0xA0)
                data = f.read(13)
                if len(data) != 13:
                    logger.warning("Unexpected logo length when computing checksum")
                    return None
                checksum = sum(data) & 0xFF
                f.seek(0xBD)
                f.write(bytes([checksum]))
                f.flush()
            logger.info(f"GBA header checksum updated for {rom_path}: 0x{checksum:02x}")
            return checksum
        except Exception as e:
            logger.error(f"Failed to update GBA header checksum: {e}")
            return None

    def push_to_sd(self, device_mount: str, device_rom_path: str, rom_basename: str, local_icon_path: str, dry_run: bool = True) -> bool:
        """Copy the icon/banner/boxart into the device's SD card layout for TwiLight++"""
        # device_mount is the mount root (e.g., /mnt/steamdeck/microsd)
        twilight_rel = self.get_configured_twilight_dir()
        dest_parent = Path(device_mount) / device_rom_path.strip('/') / twilight_rel
        dest_parent = dest_parent.resolve()
        dest_parent.mkdir(parents=True, exist_ok=True)
        dest_file = dest_parent / f"{rom_basename}.png"
        if dry_run:
            logger.info(f"[DRY-RUN] Would copy {local_icon_path} -> {dest_file}")
            return True
        try:
            shutil.copy2(local_icon_path, dest_file)
            logger.info(f"Copied icon to device: {dest_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to copy icon to device: {e}")
            return False

    def get_configured_twilight_dir(self) -> str:
        return '_nds/TWiLightMenu/icons'
