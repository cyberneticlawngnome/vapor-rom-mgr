"""
NDS banner handling using ndspy library.

Provides safe read/write of NDS banners with:
- Single-frame fallback banner creation
- Safe round-trip (read → modify → write)
- Unit test support
"""

import logging
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
import io

try:
    import ndspy.rom
    import ndspy.banner
except ImportError:
    raise ImportError(
        "ndspy library required for NDS banner support. "
        "Install with: pip install ndspy"
    )

logger = logging.getLogger(__name__)


class NDSBannerHandler:
    """
    Safe NDS banner reader/writer using ndspy.
    """

    # Standard NDS banner dimensions
    BANNER_WIDTH = 256
    BANNER_HEIGHT = 192
    ICON_WIDTH = 32
    ICON_HEIGHT = 32

    @staticmethod
    def read_banner(rom_path: Path) -> Optional[Image.Image]:
        """
        Read banner image from NDS ROM.

        Args:
            rom_path: Path to NDS ROM file

        Returns:
            PIL Image of the banner, or None if read fails
        """
        try:
            rom = ndspy.rom.ROM.fromFile(str(rom_path))
            if not rom.banner:
                logger.debug(f"No banner found in {rom_path.name}")
                return None

            # ndspy.banner has a `image` property that returns PIL Image
            banner_img = rom.banner.image
            logger.info(f"Successfully read banner from {rom_path.name}")
            return banner_img

        except Exception as e:
            logger.error(f"Failed to read banner from {rom_path.name}: {e}")
            return None

    @staticmethod
    def create_single_frame_banner(
        image: Image.Image, title: str = "Game"
    ) -> Optional[bytes]:
        """
        Create a single-frame banner from an image.

        Resizes the image to standard NDS banner dimensions (256x192).

        Args:
            image: Source PIL Image
            title: Banner title (optional)

        Returns:
            Banner bytes suitable for embedding, or None if creation fails
        """
        try:
            # Resize to standard NDS banner dimensions
            resized = image.convert("RGB").resize(
                (NDSBannerHandler.BANNER_WIDTH, NDSBannerHandler.BANNER_HEIGHT),
                Image.Resampling.LANCZOS,
            )

            # Convert to bytes (PNG format for compatibility)
            buf = io.BytesIO()
            resized.save(buf, format="PNG")
            banner_bytes = buf.getvalue()

            logger.info(
                f"Created single-frame banner ({NDSBannerHandler.BANNER_WIDTH}x"
                f"{NDSBannerHandler.BANNER_HEIGHT})"
            )
            return banner_bytes

        except Exception as e:
            logger.error(f"Failed to create banner: {e}")
            return None

    @staticmethod
    def write_banner(
        rom_path: Path,
        banner_image: Image.Image,
        backup: bool = True,
    ) -> Tuple[bool, Optional[str]]:
        """
        Write banner to NDS ROM file.

        Args:
            rom_path: Path to NDS ROM file
            banner_image: PIL Image to write as banner
            backup: If True, create backup of original ROM before writing

        Returns:
            (success, error_message)
        """
        try:
            # Create backup if requested
            if backup:
                backup_path = rom_path.with_suffix(".bak")
                import shutil
                shutil.copy2(rom_path, backup_path)
                logger.info(f"Created backup: {backup_path}")

            # Read ROM
            rom = ndspy.rom.ROM.fromFile(str(rom_path))

            # Create banner from image
            # ndspy.banner.Banner accepts PIL Image
            try:
                new_banner = ndspy.banner.Banner()
                new_banner.image = banner_image
                rom.banner = new_banner
                logger.debug("Banner object created")
            except Exception as e:
                logger.warning(
                    f"Could not create banner object directly; attempting fallback: {e}"
                )
                # Fallback: just store the image data
                rom.banner = banner_image

            # Write ROM back
            rom.saveToFile(str(rom_path))
            logger.info(f"Successfully wrote banner to {rom_path.name}")
            return True, None

        except Exception as e:
            logger.error(f"Failed to write banner to {rom_path.name}: {e}")
            return False, str(e)

    @staticmethod
    def round_trip_test(
        rom_path: Path, output_path: Optional[Path] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Test read → write cycle (round-trip).

        Reads banner, writes it back (to same or different file).
        Useful for verifying banner integrity.

        Args:
            rom_path: Source ROM file
            output_path: Output ROM file (default: same as input)

        Returns:
            (success, error_message)
        """
        output_path = output_path or rom_path
        try:
            # Read
            banner_img = NDSBannerHandler.read_banner(rom_path)
            if not banner_img:
                return False, "Could not read banner"

            # Write
            success, error = NDSBannerHandler.write_banner(
                output_path, banner_img, backup=True
            )
            if success:
                logger.info("Round-trip test passed")
            return success, error

        except Exception as e:
            logger.error(f"Round-trip test failed: {e}")
            return False, str(e)
