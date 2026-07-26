"""
Unit tests for NDS banner handling.
"""

import pytest
from pathlib import Path
from PIL import Image
import io
import tempfile

# Conditionally import ndspy-dependent module
try:
    from vapor.assets.ndspy_banner import NDSBannerHandler
    NDSPY_AVAILABLE = True
except ImportError:
    NDSPY_AVAILABLE = False


@pytest.mark.skipif(not NDSPY_AVAILABLE, reason="ndspy not installed")
class TestNDSBannerHandler:
    """Test NDS banner read/write functionality."""

    @pytest.fixture
    def sample_image(self) -> Image.Image:
        """Create a sample image for testing."""
        return Image.new("RGB", (512, 384), color=(255, 0, 0))

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_create_single_frame_banner(self, sample_image: Image.Image) -> None:
        """Test creation of single-frame banner."""
        banner_bytes = NDSBannerHandler.create_single_frame_banner(sample_image, title="Test")

        assert banner_bytes is not None
        assert len(banner_bytes) > 0
        assert banner_bytes[:4] == b"\x89PNG"  # PNG magic number

    def test_create_banner_from_various_sizes(self) -> None:
        """Test banner creation from various image sizes."""
        for width, height in [(100, 100), (512, 384), (1024, 768)]:
            img = Image.new("RGB", (width, height), color=(0, 255, 0))
            banner_bytes = NDSBannerHandler.create_single_frame_banner(img)
            assert banner_bytes is not None
            assert len(banner_bytes) > 0

    def test_create_banner_invalid_image(self) -> None:
        """Test banner creation with invalid image data."""
        # Attempt with None should fail gracefully
        result = NDSBannerHandler.create_single_frame_banner(None)
        assert result is None

    def test_banner_dimensions(self, sample_image: Image.Image) -> None:
        """Test that created banner has correct dimensions."""
        banner_bytes = NDSBannerHandler.create_single_frame_banner(sample_image)
        assert banner_bytes is not None

        # Read back the banner
        buf = io.BytesIO(banner_bytes)
        banner_img = Image.open(buf)
        assert banner_img.size == (
            NDSBannerHandler.BANNER_WIDTH,
            NDSBannerHandler.BANNER_HEIGHT,
        )

    def test_round_trip_with_mock_rom(self, temp_dir: Path, sample_image: Image.Image) -> None:
        """Test round-trip read/write (mocked, no real ROM)."""
        # Note: This is a simplified test. Real round-trip requires a valid NDS ROM.
        # In production, use actual NDS test ROMs or mock ndspy.rom
        banner_bytes = NDSBannerHandler.create_single_frame_banner(sample_image)
        assert banner_bytes is not None
        assert len(banner_bytes) > 0

    def test_banner_color_preservation(self) -> None:
        """Test that banner creation preserves image colors reasonably."""
        # Create a solid-color image
        img = Image.new("RGB", (256, 192), color=(200, 100, 50))
        banner_bytes = NDSBannerHandler.create_single_frame_banner(img)
        assert banner_bytes is not None

        # Read back and check it's still roughly the same color
        buf = io.BytesIO(banner_bytes)
        banner_img = Image.open(buf)
        # Sample center pixel (allowing for JPEG/compression artifacts)
        center_pixel = banner_img.getpixel((128, 96))
        # Should be roughly (200, 100, 50) - allow some tolerance for compression
        assert 180 <= center_pixel[0] <= 220  # Red
        assert 80 <= center_pixel[1] <= 120   # Green
        assert 30 <= center_pixel[2] <= 70    # Blue
