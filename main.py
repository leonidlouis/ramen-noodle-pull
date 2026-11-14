"""food-picture-01 entry: writes assets/ramen.jpg to <output>/entry.png byte for byte.

The contest reads the file type from its first bytes, so JPEG content under the
name entry.png is allowed. Outside the grader, MAKEFUN_OUTPUT_DIR stands in for /output:

    MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import os
import struct
import sys
import tempfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "assets" / "ramen.jpg"
MAX_BYTES = 1024 * 1024
MAX_SIDE = 1024

PNG_SIG = b"\x89PNG\r\n\x1a\n"
JPEG_SIG = b"\xff\xd8\xff"


class InvalidImage(Exception):
    pass


# JPEG markers that stand alone (no length field): TEM, RST0-RST7.
STANDALONE = {0x01, *range(0xD0, 0xD8)}
# SOF0-SOF15 minus DHT (C4), JPG (C8) and DAC (CC).
SOF_MARKERS = set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}


def jpeg_size(data):
    """Walk the JPEG segments, return (width, height) from SOF, and require the EOI marker."""
    size = None
    i = 2  # past SOI
    n = len(data)
    while True:
        if i >= n or data[i] != 0xFF:
            raise InvalidImage(f"JPEG: expected a marker at byte {i}")
        while i < n and data[i] == 0xFF:  # fill bytes
            i += 1
        if i >= n:
            raise InvalidImage("JPEG: truncated at a marker")
        marker = data[i]
        i += 1
        if marker == 0xD9:  # EOI
            break
        if marker in STANDALONE:
            continue
        if marker == 0xD8:
            raise InvalidImage(f"JPEG: unexpected second SOI at byte {i - 2}")
        if i + 2 > n:
            raise InvalidImage("JPEG: truncated segment length")
        length = struct.unpack_from(">H", data, i)[0]
        if length < 2 or i + length > n:
            raise InvalidImage(f"JPEG: segment 0xFF{marker:02X} at byte {i - 2} runs past the end")
        if marker in SOF_MARKERS:
            if length < 8:
                raise InvalidImage("JPEG: SOF segment too short")
            h, w = struct.unpack_from(">HH", data, i + 3)
            size = (w, h)
        i += length
        if marker == 0xDA:  # SOS: skip entropy-coded data up to the next real marker
            if size is None:
                raise InvalidImage("JPEG: scan data before any SOF segment")
            while True:
                j = data.find(b"\xff", i)
                if j < 0 or j + 1 >= n:
                    raise InvalidImage("JPEG: no end-of-image marker (file truncated?)")
                nxt = data[j + 1]
                if nxt == 0x00 or 0xD0 <= nxt <= 0xD7:  # stuffed byte or restart marker
                    i = j + 2
                    continue
                i = j
                break
    if size is None:
        raise InvalidImage("JPEG: no SOF segment, so no dimensions")
    if i != n:
        raise InvalidImage(f"JPEG: {n - i} bytes after the end-of-image marker")
    return size


def png_size(data):
    """Walk every PNG chunk, check its CRC, return (width, height) from IHDR, and require IEND last."""
    i = len(PNG_SIG)
    n = len(data)
    size = None
    seen_idat = False
    while True:
        if i + 8 > n:
            raise InvalidImage("PNG: truncated before IEND")
        length, kind = struct.unpack_from(">I4s", data, i)
        body_end = i + 8 + length
        if body_end + 4 > n:
            raise InvalidImage(f"PNG: chunk {kind!r} at byte {i} runs past the end")
        body = data[i + 8:body_end]
        crc = struct.unpack_from(">I", data, body_end)[0]
        if zlib.crc32(kind + body) != crc:
            raise InvalidImage(f"PNG: bad CRC in chunk {kind!r} at byte {i}")
        if size is None:
            if kind != b"IHDR" or length != 13:
                raise InvalidImage("PNG: first chunk is not a valid IHDR")
            size = struct.unpack_from(">II", body)
        elif kind == b"IDAT":
            seen_idat = True
        i = body_end + 4
        if kind == b"IEND":
            break
    if not seen_idat:
        raise InvalidImage("PNG: no IDAT chunk (no image data)")
    if i != n:
        raise InvalidImage(f"PNG: {n - i} bytes after IEND")
    return size


def validate(data):
    if len(data) > MAX_BYTES:
        raise InvalidImage(f"file is {len(data)} bytes, over the {MAX_BYTES} byte limit")
    if data.startswith(PNG_SIG):
        w, h = png_size(data)
    elif data.startswith(JPEG_SIG):
        w, h = jpeg_size(data)
    else:
        raise InvalidImage("file is neither a PNG nor a JPEG")
    if w == 0 or h == 0:
        raise InvalidImage(f"image header gives an empty {w}x{h} picture")
    if w > MAX_SIDE or h > MAX_SIDE:
        raise InvalidImage(f"image is {w}x{h}, over {MAX_SIDE}x{MAX_SIDE}")
    return w, h


def main(source=SOURCE):
    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output")
    try:
        data = Path(source).read_bytes()
    except OSError as e:
        print(f"error: cannot read {source}: {e.strerror or e}", file=sys.stderr)
        return 1
    try:
        w, h = validate(data)
    except InvalidImage as e:
        print(f"error: {source}: {e}", file=sys.stderr)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    # Write to a temp file in the same directory, then rename: never a half-written entry.png.
    fd, tmp = tempfile.mkstemp(dir=out_dir, prefix=".entry-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, 0o644)  # mkstemp makes 0600; the grader may read as another user
        os.replace(tmp, out_dir / "entry.png")
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    print(f"wrote {out_dir / 'entry.png'} ({len(data)} bytes, {w}x{h})")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
