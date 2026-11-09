"""Outcome tests: no GPU, network, vendor execution or downloaded fonts."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops, ImageFont

from src.bubble_renderer import render_bubbles, wrap_text
from src.script_formatter import format_script, parse_script
from src.webtoon_stitcher import stitch_episode


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


class FilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="factory-test-", dir=Path(__file__).resolve().parents[1])
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)


class FormatterTests(FilesTest):
    def test_formatter_does_not_overwrite_hand_edited_chunk(self):
        source = write_json(self.root / "input.json", {"cuts": [{"id": "cut_1", "description": "test"}]})
        output = self.root / "chunks"
        index = format_script(source, output)
        native = output / index["batches"][0]["text"]
        native.write_text("hand edited direction", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "modified"):
            format_script(source, output)
        self.assertEqual(native.read_text(), "hand edited direction")

    def test_explicit_page_capacity_and_multiple_speakers(self):
        parsed = parse_script('민「안녕」 준「반가워」')
        self.assertEqual([d["position"] for d in parsed["cuts"][0]["dialogue"]], ["auto", "auto"])
        render_bubbles(Image.new("RGB", (800, 650), "gray"), parsed["cuts"][0]["dialogue"])
        source = write_json(self.root / "input.json", {"cuts": [
            {"id": f"cut_{i}", "page": 1, "description": "한 페이지"} for i in range(6)]})
        with self.assertRaises(ValueError):
            format_script(source, self.root / "out", cuts_per_page=4)

    def test_five_pages_become_two_two_one_without_loss(self):
        episode = {"title": "분할 검증", "cuts": [
            {"id": f"cut_{i:03}", "page": i, "description": f"장면 {i}",
             "camera": {"shot": "CU", "angle": "low-angle", "lens": "85mm", "position": "profile"},
             "dialogue": [{"speaker": "민", "text": f"대사 {i}", "position": "top-left", "type": "normal"}],
             "image": f"../art/{i}.png", "gap_after": 135}
            for i in range(1, 6)]}
        source = write_json(self.root / "input" / "episode.json", episode)
        dest = self.root / "formatted"
        format_script(source, dest)
        normalized = json.loads((dest / "episode.json").read_text(encoding="utf-8"))
        self.assertEqual([x["id"] for x in normalized["cuts"]], [x["id"] for x in episode["cuts"]])
        self.assertEqual([x["page"] for x in normalized["cuts"]], [1, 2, 3, 4, 5])
        batches = sorted(dest.glob("chunk_*.txt"))
        self.assertEqual(len(batches), 3)
        for path, page_count in zip(batches, (2, 2, 1)):
            native = path.read_text(encoding="utf-8")
            self.assertIn("1P", native)
            self.assertEqual("2P" in native, page_count == 2)
            self.assertNotIn("3P", native)
            self.assertIn("タイトル", native)
        for original, cut in zip(episode["cuts"], normalized["cuts"]):
            self.assertEqual(cut["dialogue"], original["dialogue"])
            self.assertEqual(cut["camera"], original["camera"])
            self.assertEqual(cut["gap_after"], 135)
            self.assertEqual((dest / cut["image"]).resolve(), (source.parent / original["image"]).resolve())

    def test_plain_text_tagging_and_automatic_page_boundaries(self):
        result = parse_script("\ufeff[CU, low-angle, 85mm, profile] 첫 장면\n둘째 장면\n셋째 장면", cuts_per_page=2)
        cuts = result["cuts"]
        self.assertEqual(len(cuts), 3)
        self.assertEqual([c["page"] for c in cuts], [1, 1, 2])
        self.assertEqual(cuts[0]["camera"], {"shot": "CU", "angle": "low-angle", "lens": "85mm", "position": "profile"})
        self.assertTrue(all(len(c["camera"]) == 4 for c in cuts))
        self.assertIn("첫 장면", cuts[0]["description"])

    def test_empty_and_invalid_page_capacity_rejected(self):
        with self.assertRaises(ValueError):
            parse_script("  \n")
        with self.assertRaises(ValueError):
            parse_script("장면", cuts_per_page=0)

    def test_duplicate_id_in_json_rejected(self):
        cut = {"id": "same", "page": 1, "description": "장면"}
        source = write_json(self.root / "input.json", {"cuts": [cut, cut]})
        with self.assertRaises(ValueError):
            format_script(source, self.root / "formatted")


class LetteringTests(unittest.TestCase):
    def test_per_entry_font_size_changes_sfx_instead_of_silently_using_global_size(self):
        base = Image.new('RGB', (800, 500), 'white')
        small = render_bubbles(base, [{'text': '톡', 'type': 'sfx', 'box': [.1, .1, .6, .6], 'font_size': 24}], font_size=24)
        large = render_bubbles(base, [{'text': '톡', 'type': 'sfx', 'box': [.1, .1, .6, .6], 'font_size': 64}], font_size=24)
        self.assertNotEqual(small.tobytes(), large.tobytes())
        with self.assertRaises(ValueError):
            render_bubbles(base, [{'text': '톡', 'font_size': True}])

    def test_korean_wrap_preserves_every_character_and_newlines(self):
        font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 28) if Path("C:/Windows/Fonts/malgun.ttf").exists() else None
        if font is None:
            from src.bubble_renderer import _load_font
            font = _load_font(None, 28, "한글")
        text = "가나다라마바사아자차카타파하\n두번째줄"
        lines = wrap_text(text, font, 95)
        self.assertEqual("".join(lines), text.replace("\n", ""))
        self.assertTrue(all(font.getlength(line) <= 95 for line in lines))
        self.assertIn("두", "".join(lines))

    def test_each_balloon_kind_renders_and_preserves_original(self):
        original = Image.new("RGB", (800, 650), "#90b0a0")
        unchanged = original.copy()
        for kind in ("normal", "shout", "thought", "narration", "sfx"):
            with self.subTest(kind=kind):
                result = render_bubbles(original, [{"text": "한글 대사\n두 번째 줄", "type": kind,
                                                    "box": [0.05, 0.05, 0.75, 0.45]}])
                self.assertEqual(result.size, original.size)
                self.assertIsNotNone(ImageChops.difference(result.convert("RGB"), original).getbbox())
                self.assertIsNone(ImageChops.difference(original, unchanged).getbbox())
                self.assertEqual(result.convert("RGB").getpixel((799, 649)), original.getpixel((799, 649)))

    def test_invalid_font_overflow_and_overlap_fail_instead_of_dropping_text(self):
        art = Image.new("RGB", (800, 600), "gray")
        with self.assertRaises((ValueError, OSError)):
            render_bubbles(art, [{"text": "한글"}], font_path="missing-font.ttf")
        with self.assertRaises(ValueError):
            render_bubbles(art, [{"text": "긴대사" * 200, "box": [0.01, 0.01, 0.1, 0.1]}])
        with self.assertRaises(ValueError):
            render_bubbles(art, [{"text": "첫 대사", "box": [0.1, 0.1, 0.5, 0.4]},
                                {"text": "겹친 대사", "box": [0.1, 0.1, 0.5, 0.4]}])


class StitchTests(FilesTest):
    def test_authored_matte_and_fade_gutter(self):
        source = self.manifest(2)
        data = json.loads(source.read_text(encoding='utf-8'))
        data['cuts'][0].update(gap_after=30, gap_gradient_after=['#FFFFFF','#071523'])
        Image.new('RGBA',(80,40),(0,0,0,0)).save(self.root/'transparent.png')
        data['cuts'][1].update(image='transparent.png',matte='#071523')
        write_json(source,data)
        record_path = stitch_episode(source,self.root/'fade',top_padding=0,bottom_padding=0)
        record = json.loads(record_path.read_text(encoding='utf-8'))
        with Image.open(record_path.parent/'full_strip.png') as im:
            self.assertEqual(im.getpixel((0,400)),(255,255,255))
            self.assertEqual(im.getpixel((0,429)),(7,21,35))
            self.assertEqual(im.getpixel((0,430)),(7,21,35))
        data['cuts'][0]['gap_gradient_after']=['#FFFFFF']
        write_json(source,data)
        with self.assertRaisesRegex(ValueError,'two colors'):
            stitch_episode(source,self.root/'bad-fade')

    def test_inset_panel_width_placement_and_bounds(self):
        source = self.manifest(1)
        data = json.loads(source.read_text(encoding='utf-8'))
        data['cuts'][0].update(display_width=600, x=160)
        write_json(source, data)
        path = stitch_episode(source, self.root/'inset', top_padding=0, bottom_padding=0)
        record = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual((record['cuts'][0]['x'], record['cuts'][0]['width'], record['cuts'][0]['height']), (160,600,300))
        with Image.open(path.parent/'full_strip.png') as im:
            self.assertEqual(im.getpixel((159,100)), (255,255,255))
            self.assertEqual(im.getpixel((160,100)), (120,30,90))
            self.assertEqual(im.getpixel((760,100)), (255,255,255))
        data['cuts'][0]['x']=201
        write_json(source, data)
        with self.assertRaisesRegex(ValueError,'canvas width'):
            stitch_episode(source,self.root/'invalid-inset')

    def manifest(self, count=2):
        cuts = []
        for index in range(count):
            image = self.root / f"cut_{index}.png"
            Image.new("RGB", (400, 200 + index * 50), (120, 30 + index * 20, 90)).save(image)
            cuts.append({"id": f"cut_{index}", "image": image.name, "dialogue": []})
        return write_json(self.root / "input.json", {"title": "병합 테스트", "cuts": cuts})

    def test_dimensions_gutters_order_and_lossless_slice_reconstruction(self):
        source = self.manifest()
        record_path = stitch_episode(source, self.root / "output", padding=75, top_padding=20,
                                     bottom_padding=30, max_height=700)
        record = json.loads(record_path.read_text(encoding="utf-8"))
        with Image.open(record_path.parent / "full_strip.png") as full:
            self.assertEqual(full.size, (800, 20 + 400 + 75 + 500 + 30))
            self.assertEqual(full.getpixel((50, 419)), (120, 30, 90))
            self.assertEqual(full.getpixel((50, 420)), (255, 255, 255))
            self.assertEqual(full.getpixel((50, 494)), (255, 255, 255))
            self.assertEqual(full.getpixel((50, 495)), (120, 50, 90))
            restored = Image.new("RGB", full.size)
            offset = 0
            for part in record["parts"]:
                with Image.open(record_path.parent / part["path"]) as segment:
                    self.assertEqual(segment.width, 800)
                    self.assertLessEqual(segment.height, 700)
                    self.assertEqual(part["y"], offset)
                    restored.paste(segment, (0, offset))
                    offset += segment.height
            self.assertEqual(offset, full.height)
            self.assertIsNone(ImageChops.difference(full, restored).getbbox())

    def test_missing_art_no_partial_deliverable_and_memory_limit(self):
        source = write_json(self.root / "input.json", {"cuts": [{"id": "missing", "image": "missing.png"}]})
        with self.assertRaises(OSError):
            stitch_episode(source, self.root / "output")
        self.assertFalse((self.root / "output" / "manifest.json").exists())
        source = self.manifest()
        with self.assertRaisesRegex(ValueError, "pixels"):
            stitch_episode(source, self.root / "output", max_pixels=100)

    def test_rerun_protection_and_stale_part_cleanup(self):
        source = self.manifest(3)
        output = self.root / "out"
        stitch_episode(source, output, max_height=700)
        old_parts = set(output.glob("slice_*.png"))
        with self.assertRaises(FileExistsError):
            stitch_episode(source, output)
        source = self.manifest(1)
        stitch_episode(source, output, max_height=1280, overwrite=True)
        self.assertEqual(len(list(output.glob("slice_*.png"))), 1)
        self.assertTrue(any(not p.exists() for p in old_parts))

    def test_smart_boundaries_keep_whole_cuts_and_reject_taller_than_limit(self):
        source = self.manifest(3)
        path = stitch_episode(source, self.root / "smart", max_height=750)
        data = json.loads(path.read_text(encoding="utf-8"))
        for part in data["parts"][:-1]:
            boundary = part["y"] + part["height"]
            self.assertFalse(any(c["y"] < boundary < c["y"] + c["height"] for c in data["cuts"]))
        with self.assertRaisesRegex(ValueError, "never sliced"):
            stitch_episode(source, self.root / "too_short", max_height=300)
        self.assertFalse((self.root / "too_short" / "manifest.json").exists())

    def test_configurable_width_black_gutter_and_modified_output_protection(self):
        source = self.manifest(1)
        data = json.loads(source.read_text(encoding="utf-8"))
        data["cuts"][0]["id"] = "scene.001"
        write_json(source, data)
        path = stitch_episode(source, self.root / "black", width=600, background="#000000")
        data = json.loads(path.read_text(encoding="utf-8"))
        full_path = path.parent / data["full"]["path"]
        with Image.open(full_path) as image:
            self.assertEqual(image.width, 600)
            self.assertEqual(image.getpixel((0, 0)), (0, 0, 0))
        full_path.write_bytes(b"user edit")
        with self.assertRaisesRegex(ValueError, "modified"):
            stitch_episode(source, path.parent, overwrite=True)
        self.assertEqual(full_path.read_bytes(), b"user edit")

    def test_forged_manifest_does_not_delete_unowned_file(self):
        source = self.manifest(1)
        output = self.root / "forged"
        victim = output / "slice_999.png"
        victim.parent.mkdir()
        victim.write_bytes(b"private art")
        write_json(output / "manifest.json", {"generator": "webtoon-factory", "schema_version": 1,
                                              "full": {"path": victim.name}, "parts": []})
        with self.assertRaises(ValueError):
            stitch_episode(source, output, overwrite=True)
        self.assertEqual(victim.read_bytes(), b"private art")


class TenCutPipelineTests(FilesTest):
    def test_offline_demo_builds_placeholder_art_without_unused_guide_assets(self):
        from src.demo import run_demo
        example = json.loads((Path(__file__).resolve().parents[1] / "workspace/01_scripts/example.json").read_text(encoding="utf-8"))
        workspace = self.root / "workspace"
        write_json(workspace / "01_scripts/example.json", example)
        output = run_demo(workspace)
        manifest = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(len(manifest['cuts']), 10)
        self.assertEqual(len(list((workspace / '05_rendered_cuts/demo').glob('*.png'))), 10)
        self.assertFalse((workspace / '02_conti_atari').exists())
        self.assertFalse((workspace / '03_backgrounds').exists())

    def test_demo_refuses_escaped_path_before_overwriting_any_art(self):
        from src.demo import run_demo
        example = json.loads((Path(__file__).resolve().parents[1] / "workspace" / "01_scripts" / "example.json").read_text(encoding="utf-8"))
        workspace = self.root / "workspace"
        example["cuts"][0]["image"] = "../../important.png"
        write_json(workspace / "01_scripts" / "example.json", example)
        important = self.root / "important.png"
        important.write_bytes(b"original art must survive")
        with self.assertRaises(ValueError):
            run_demo(workspace, overwrite=True)
        self.assertEqual(important.read_bytes(), b"original art must survive")

    def test_ten_placeholder_cuts_two_chunks_korean_webtoon_artifacts(self):
        cuts = []
        for i in range(10):
            path = self.root / 'art' / f"{i}.png"
            path.parent.mkdir(exist_ok=True)
            Image.new("RGB", (384, 512), "#9db6ab").save(path)
            self.assertGreater(path.stat().st_size, 0)
            cuts.append({"id": f"cut_{i:03d}", "description": f"테스트 장면 {i}",
                         "image": f"art/{i}.png",
                         "dialogue": [{"speaker": "테스트", "text": f"{i+1}번째 컷입니다.", "position": "auto"}]})
        source = write_json(self.root / "ten.json", {"title": "열 컷 통합 검증", "cuts": cuts})
        formatted = self.root / "chunks"
        index = format_script(source, formatted, cuts_per_page=4)
        self.assertEqual([b["page_count"] for b in index["batches"]], [2, 1])
        self.assertEqual([len(b["cut_ids"]) for b in index["batches"]], [8, 2])
        final = stitch_episode(formatted / "episode.json", self.root / "output")
        data = json.loads(final.read_text(encoding="utf-8"))
        self.assertEqual(len(data["cuts"]), 10)
        self.assertGreater(len(data["parts"]), 1)
        for record in [data["full"], *data["parts"]]:
            path = final.parent / record["path"]
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 0)
            with Image.open(path) as image:
                self.assertEqual(image.width, 800)
                self.assertGreater(image.height, 0)


if __name__ == "__main__":
    unittest.main()
