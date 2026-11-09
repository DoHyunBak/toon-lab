"""Readiness verifies real glyphs, originals and disk writes, without model calls."""
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from collections import namedtuple
from unittest.mock import patch

from PIL import Image

from src.bubble_renderer import BubbleLayoutError
from src.runtime_check import check_runtime


class RuntimeCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="runtime-check-", dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        folder = self.root / "workspace/references/ref_0001"
        folder.mkdir(parents=True)
        image = folder / "original.png"
        Image.new("RGB", (16, 24), "#abc123").save(image)
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        metadata = {"id": "ref_0001", "title": "테스트 예시",
                    "original": {"path": "original.png", "format": "PNG", "width": 16, "height": 24,
                                 "bytes": image.stat().st_size, "sha256": digest},
                    "observations": [{"topic": "조명", "note": "따뜻한 측광."}],
                    "production_application": {"layout": "한 열 읽기 흐름"}}
        (folder / "reference.json").write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        self.catalog = folder.parent / "catalog.json"
        catalog = {"schema_version": 1, "references": [{"id": "ref_0001", "title": "테스트 예시",
                   "original": "ref_0001/original.png", "metadata": "ref_0001/reference.json",
                   "sha256": digest, "tags": []}]}
        self.catalog.write_text(json.dumps(catalog), encoding="utf-8")

    def check(self):
        return check_runtime(project_root=self.root, reference_catalog=self.catalog)

    def test_default_text_only_readiness_never_requires_or_reads_image_library(self):
        self.catalog.unlink()
        before = sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*"))
        with patch("src.reference_guidance.load_references") as references:
            result = check_runtime(project_root=self.root)
        self.assertEqual(result["status"], "ready", result)
        self.assertNotEqual(result["checks"]["references"]["status"], "blocked")
        references.assert_not_called()
        self.assertEqual(sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*")), before)

    def test_python_floor_matches_pillow_13_requirement(self):
        version = namedtuple("Version", "major minor micro")
        for minor, expected in ((10, "blocked"), (11, "pass")):
            with self.subTest(minor=minor), patch("src.runtime_check.sys.version_info", version(3, minor, 0)):
                result = self.check()["checks"]["python"]
                self.assertEqual(result["status"], expected)
                if minor == 10:
                    self.assertIn("3.11", result["action"])

    def test_real_font_reference_and_png_roundtrip_pass_and_leave_no_temp_files(self):
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        result = self.check()
        self.assertEqual(result["status"], "ready", result)
        self.assertEqual(result["checks"]["references"]["count"], 1)
        self.assertEqual(result["image_generation"]["availability"], "not_locally_detectable")
        self.assertEqual(sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*")), before)

    def test_missing_reference_original_blocks_with_action(self):
        (self.catalog.parent / "ref_0001/original.png").unlink()
        result = self.check()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["checks"]["references"]["status"], "blocked")
        self.assertIn("Restore", result["checks"]["references"]["action"])
        self.assertEqual(result["checks"]["workspace"]["status"], "pass")

    def test_missing_or_empty_catalog_blocks(self):
        for content in (None, '{"schema_version": 1, "references": []}'):
            with self.subTest(content=content):
                if content is None:
                    self.catalog.unlink()
                else:
                    self.catalog.write_text(content, encoding="utf-8")
                self.assertEqual(self.check()["checks"]["references"]["status"], "blocked")

    def test_missing_korean_font_blocks_without_changing_other_checks(self):
        with patch("src.bubble_renderer._load_font", side_effect=BubbleLayoutError("No usable Korean font")):
            result = self.check()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["checks"]["korean_font"]["status"], "blocked")
        self.assertIn("WEBTOON_FONT", result["checks"]["korean_font"]["action"])
        self.assertEqual(result["checks"]["references"]["status"], "pass")

    def test_unwritable_workspace_reports_failure(self):
        with patch("src.runtime_check.tempfile.TemporaryDirectory", side_effect=PermissionError("Read only workspace")):
            result = self.check()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["checks"]["workspace"]["status"], "blocked")
        self.assertIn("writable", result["checks"]["workspace"]["action"])

    def test_missing_pillow_is_actionable_instead_of_import_crash(self):
        real_import = importlib.import_module

        def without_pillow(name):
            if name == "PIL":
                raise ModuleNotFoundError("No module named 'PIL'")
            return real_import(name)

        with patch("src.runtime_check.importlib.import_module", side_effect=without_pillow):
            result = self.check()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["checks"]["pillow"]["status"], "blocked")
        self.assertIn("requirements.txt", result["checks"]["pillow"]["action"])

    def test_custom_relative_catalog_is_relative_to_project_root(self):
        result = check_runtime(project_root=self.root, reference_catalog="workspace/references/catalog.json")
        self.assertEqual(result["checks"]["references"]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
