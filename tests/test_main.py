import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN = ROOT / "main.py"
sys.path.insert(0, str(ROOT))

import main  # noqa: E402


def run_main(out_dir, *args, cwd=None):
    env = dict(os.environ, MAKEFUN_OUTPUT_DIR=str(out_dir))
    return subprocess.run(
        [sys.executable, str(MAIN), *args],
        env=env, cwd=cwd, capture_output=True, text=True, timeout=30,
    )


def make_png(width, height):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x00" * width for _ in range(height))
    return main.PNG_SIG + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def make_jpeg(width, height):
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof0 = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, height, width, 1) + b"\x01\x11\x00"
    return b"\xff\xd8" + app0 + sof0 + b"\xff\xd9"


class RunTwice(unittest.TestCase):
    def test_two_runs_write_identical_bytes(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            # Run from different cwds: paths must resolve relative to main.py.
            r1 = run_main(Path(a) / "out", cwd=a)
            r2 = run_main(Path(b) / "nested" / "out", cwd=b)
            self.assertEqual(r1.returncode, 0, r1.stderr)
            self.assertEqual(r2.returncode, 0, r2.stderr)
            out1 = (Path(a) / "out" / "entry.png").read_bytes()
            out2 = (Path(b) / "nested" / "out" / "entry.png").read_bytes()
            self.assertEqual(out1, out2)
            self.assertEqual(out1, main.SOURCE.read_bytes())

    def test_output_meets_limits(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(run_main(d).returncode, 0)
            data = (Path(d) / "entry.png").read_bytes()
            self.assertLessEqual(len(data), main.MAX_BYTES)
            self.assertTrue(data.startswith(main.JPEG_SIG))
            w, h = main.validate(data)
            self.assertEqual((w, h), (1024, 1024))


class Validate(unittest.TestCase):
    def test_png_dimensions(self):
        self.assertEqual(main.validate(make_png(3, 2)), (3, 2))

    def test_jpeg_dimensions(self):
        self.assertEqual(main.validate(make_jpeg(640, 480)), (640, 480))

    def test_too_wide_refused(self):
        with self.assertRaisesRegex(main.InvalidImage, "1025x10"):
            main.validate(make_jpeg(1025, 10))
        with self.assertRaisesRegex(main.InvalidImage, "10x1025"):
            main.validate(make_png(10, 1025))

    def test_too_big_refused(self):
        data = make_jpeg(8, 8)
        big = data[:-2] + b"\x00" * (main.MAX_BYTES) + data[-2:]
        with self.assertRaisesRegex(main.InvalidImage, "byte limit"):
            main.validate(big)

    def test_not_an_image_refused(self):
        with self.assertRaisesRegex(main.InvalidImage, "neither"):
            main.validate(b"GIF89a" + b"\x00" * 20)

    def test_truncated_jpeg_refused(self):
        with self.assertRaises(main.InvalidImage):
            main.validate(make_jpeg(8, 8)[:12])


class BadFileRefused(unittest.TestCase):
    def test_bad_file_exits_nonzero_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.jpg"
            bad.write_bytes(b"not an image at all")
            out = Path(d) / "out"
            r = run_main(out, str(bad))
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("error", r.stderr)
            self.assertFalse((out / "entry.png").exists())

    def test_oversized_dimensions_exit_nonzero(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "huge.jpg"
            bad.write_bytes(make_jpeg(2048, 2048))
            r = run_main(Path(d) / "out", str(bad))
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("2048x2048", r.stderr)


if __name__ == "__main__":
    unittest.main()
