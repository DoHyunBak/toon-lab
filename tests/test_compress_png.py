import io
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from PIL import Image, PngImagePlugin

from compress_png import SIGNATURE, chunk, compress_file, inspect_png, optimize


class CompressionTests(unittest.TestCase):
    def encoded(self, mode):
        image = Image.new(mode, (48, 73))
        if mode == "P":
            image.putpalette([i for value in range(256) for i in (value, 255 - value, value)])
            image.info["transparency"] = 0
        info = PngImagePlugin.PngInfo()
        info.add_text("Copyright", "Own test fixture")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", compress_level=0, pnginfo=info)
        return buffer.getvalue()

    def test_modes_pixels_metadata_and_reduction(self):
        for mode in ("RGB", "RGBA", "P", "L", "LA", "I;16", "1"):
            with self.subTest(mode=mode):
                data = self.encoded(mode)
                result, report = optimize(data)
                with Image.open(io.BytesIO(data)) as before, Image.open(io.BytesIO(result)) as after:
                    self.assertEqual(before.mode, after.mode)
                    self.assertEqual(before.tobytes(), after.tobytes())
                    self.assertEqual(before.convert("RGBA").tobytes(), after.convert("RGBA").tobytes())
                    self.assertEqual(before.info, after.info)
                self.assertLess(len(result), len(data))
                self.assertTrue(report["verification"]["non_idat_chunks_identical"])

    def test_never_larger_and_repeat_safe(self):
        first, _ = optimize(self.encoded("RGBA"))
        second, _ = optimize(first)
        self.assertLessEqual(len(second), len(first))

    def test_corrupt_truncated_and_animation_rejected(self):
        data = self.encoded("RGB")
        corrupt = bytearray(data)
        corrupt[29] ^= 1
        animated = data[:33] + chunk(b"acTL", struct.pack(">II", 1, 0)) + data[33:]
        for bad in (bytes(corrupt), data[:-1], data + b"extra", animated):
            with self.subTest(length=len(bad)), self.assertRaises(ValueError):
                optimize(bad)

    def test_adam7_scanlines_preserved(self):
        # One-pixel Adam7 fixture has only pass 1 populated.
        data = (SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 1))
                + chunk(b"IDAT", zlib.compress(b"\0\x12\x34\x56\x78", 0)) + chunk(b"IEND", b""))
        result, _ = optimize(data)
        with Image.open(io.BytesIO(result)) as decoded:
            self.assertEqual(decoded.getpixel((0, 0)), (18, 52, 86, 120))

    def test_file_source_untouched_and_existing_paths_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "in.png", Path(directory) / "out.png"
            data = self.encoded("RGB")
            source.write_bytes(data)
            with self.assertRaises(ValueError):
                compress_file(source, source)
            report = compress_file(source, target)
            self.assertEqual(source.read_bytes(), data)
            self.assertEqual(report["output_bytes"], target.stat().st_size)
            self.assertTrue(target.with_suffix(".png.compression.json").exists())
            with self.assertRaises(ValueError):
                compress_file(source, target)


if __name__ == "__main__":
    unittest.main()
