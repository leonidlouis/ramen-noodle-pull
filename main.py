"""food-picture-01 entry: writes assets/ramen.jpg to <output>/entry.png byte for byte.

The contest reads the file type from its first bytes, so JPEG content under the
name entry.png is allowed. Outside the grader, MAKEFUN_OUTPUT_DIR stands in for /output:

    MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import os
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "assets" / "ramen.jpg"
MAX_BYTES = 1024 * 1024
MAX_SIDE = 1024

PNG_SIG = b"\x89PNG\r\n\x1a\n"
JPEG_SIG = b"\xff\xd8\xff"


class InvalidImage(Exception):
    pass


def jpeg_size(data):
    i = 2
    while i + 4 <= len(data):
        marker = data[i + 1]
        length = struct.unpack(">H", data[i + 2:i + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + length
    raise InvalidImage("no SOF marker found in JPEG")


def png_size(data):
    if data[12:16] != b"IHDR":
        raise InvalidImage("PNG does not start with an IHDR chunk")
    return struct.unpack(">II", data[16:24])


def validate(data):
    if len(data) > MAX_BYTES:
        raise InvalidImage(f"file is {len(data)} bytes, over the {MAX_BYTES} byte limit")
    if data.startswith(PNG_SIG):
        w, h = png_size(data)
    elif data.startswith(JPEG_SIG):
        w, h = jpeg_size(data)
    else:
        raise InvalidImage("file is neither a PNG nor a JPEG")
    if w > MAX_SIDE or h > MAX_SIDE:
        raise InvalidImage(f"image is {w}x{h}, over {MAX_SIDE}x{MAX_SIDE}")
    return w, h


def main(source=SOURCE):
    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output")
    data = Path(source).read_bytes()
    try:
        validate(data)
    except InvalidImage as e:
        print(f"error: {source}: {e}", file=sys.stderr)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "entry.png").write_bytes(data)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
