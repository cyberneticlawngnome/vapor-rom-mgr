import os
import tempfile
from pathlib import Path
from vapor.assets.twilight import TwiLightAssetHandler


def test_gba_header_checksum_update():
    # create a temporary dummy gba file with known logo bytes
    tmpdir = Path(tempfile.mkdtemp())
    rom = tmpdir / 'dummy.gba'
    # build data up to 0xBD
    data = bytearray(0xBD + 1)
    # set logo bytes 0xA0..0xAC = 1..13
    for i in range(13):
        data[0xA0 + i] = i + 1
    # checksum should be sum(1..13)=91 decimal
    expected = sum(range(1, 14)) & 0xFF
    rom.write_bytes(data)

    handler = TwiLightAssetHandler(cache_dir=tmpdir)
    cs = handler._update_gba_header_checksum(str(rom))
    assert cs == expected
    # ensure file byte at 0xBD updated
    b = rom.read_bytes()
    assert b[0xBD] == expected
