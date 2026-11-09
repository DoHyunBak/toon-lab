"""Production workflow: real-file import, provenance, revisions and artifact checks."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from src.factory import prepare_job, import_cut, build_job, job_status


class FactoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="factory-workflow-", dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.job = self.root / "job"
        self.source = self.root / "episode.json"
        self.data = {"title": "제작 흐름 검증", "cuts": [
            {"id": "cut_001", "page": 1, "description": "문 앞에 선 인물", "characters": [],
             "dialogue": [{"speaker": "", "text": "여기가 웹툰 공장이구나.", "type": "normal",
                           "box": [0.05, 0.05, 0.52, 0.22], "tail": [0.52, 0.26]}]}]}
        self.source.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        self.art = self.root / "art.png"
        Image.new("RGB", (512, 768), "#b3c9bd").save(self.art)
        self.prompt = self.root / "actual_prompt.txt"
        self.prompt.write_text("One quiet studio doorway, no text.", encoding="utf-8")

    def test_prepare_import_build_lifecycle_and_provenance(self):
        source_bytes = self.source.read_bytes()
        job = prepare_job(self.source, self.job)
        self.assertEqual(job["generation_input_mode"], "text_only")
        self.assertEqual(job["generation_policy_version"], "text-only-v1")
        self.assertEqual(self.source.read_bytes(), source_bytes)
        self.assertEqual(job_status(self.job)["missing"], ["cut_001"])
        brief = self.job / job["cuts"][0]["prompt_file"]
        self.assertTrue(brief.is_file() and brief.stat().st_size > 0)
        imported = import_cut(self.job, "cut_001", self.art, self.prompt)
        self.assertEqual(imported["provider"], "imagegen")
        self.assertEqual(imported["prompt"], self.prompt.read_text())
        self.assertEqual((self.job / imported["original"]).read_bytes(), self.art.read_bytes())
        self.assertEqual(job_status(self.job)["status"], "ready_to_build")
        output = build_job(self.job, min_font_size=30)
        self.assertEqual(job_status(self.job)["status"], "built")
        with Image.open(output.parent / "full_strip.png") as image:
            self.assertEqual(image.size, (800, 1400))
        self.assertEqual(job_status(self.job)["approval"], "not_reviewed")

    def test_unsupported_provider_is_rejected_without_changing_job_or_art(self):
        prepare_job(self.source, self.job)
        before = {p.relative_to(self.job): p.read_bytes() for p in self.job.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(ValueError, "Unsupported generation provider"):
            import_cut(self.job, "cut_001", self.art, self.prompt, provider="retired-backend")
        self.assertEqual({p.relative_to(self.job): p.read_bytes() for p in self.job.rglob('*') if p.is_file()}, before)

    def test_missing_art_blocks_build_without_final_output(self):
        prepare_job(self.source, self.job)
        with self.assertRaisesRegex(ValueError, "Missing"):
            build_job(self.job)
        self.assertFalse((self.job / "output" / "manifest.json").exists())

    def test_replacement_retains_original_versions_and_resets_build(self):
        prepare_job(self.source, self.job)
        first = import_cut(self.job, "cut_001", self.art)
        with self.assertRaises(FileExistsError):
            import_cut(self.job, "cut_001", self.art)
        second_art = self.root / "second.png"
        Image.new("RGB", (512, 768), "#a4bbc7").save(second_art)
        second = import_cut(self.job, "cut_001", second_art, replace=True)
        self.assertNotEqual(first["image"], second["image"])
        self.assertTrue((self.job / first["image"]).is_file())
        stored = json.loads((self.job / "job.json").read_text(encoding="utf-8"))
        self.assertEqual(len(stored["cuts"][0]["history"]), 1)
        self.assertIsNone(stored["output"])
        self.assertEqual(second["prompt_verification"], "not_recorded")

    def test_modified_import_is_detected_and_blocks_rebuild(self):
        prepare_job(self.source, self.job)
        imported = import_cut(self.job, "cut_001", self.art)
        (self.job / imported["image"]).write_bytes(b"modified outside pipeline")
        self.assertEqual(job_status(self.job)["changed"], ["cut_001"])
        with self.assertRaises(ValueError):
            build_job(self.job)

    def test_text_character_identity_reaches_brief_without_image_inputs(self):
        self.data["cuts"][0]["characters"] = ["min"]
        self.source.write_text(json.dumps(self.data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "characters"):
            prepare_job(self.source, self.job)
        characters = self.root / "characters.json"
        characters.write_text(json.dumps({"characters": {"min": {"description": "short dark hair, green jacket",
                                                                 "reference_images": []}}}), encoding="utf-8")
        job = prepare_job(self.source, self.job, characters)
        self.assertEqual(job["cuts"][0]["reference_images"], [])
        brief = (self.job / job["cuts"][0]["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn("short dark hair", brief)
        self.assertEqual(job["generation_input_mode"], "text_only")

    def test_character_image_is_rejected_before_it_is_opened(self):
        self.data["cuts"][0]["characters"] = ["min"]
        self.source.write_text(json.dumps(self.data), encoding="utf-8")
        characters = self.root / "characters.json"
        characters.write_text(json.dumps({"characters": {"min": {
            "description": "short dark hair", "reference_images": ["never-read.png"]}}}), encoding="utf-8")
        with patch("src.factory.Image.open") as image_open:
            with self.assertRaises(ValueError):
                prepare_job(self.source, self.job, characters)
        image_open.assert_not_called()
        self.assertFalse((self.job / "job.json").exists())

    def test_generation_image_fields_are_rejected_before_image_or_catalog_reads(self):
        mutations = [
            lambda data: data.update(image="never-read.png"),
            lambda data: data.update(reference_images=["never-read.png"]),
            lambda data: data.update(reference_ids=["ref_0001"]),
            lambda data: data["cuts"][0].update(image="never-read.png"),
            lambda data: data["cuts"][0].update(atari="never-read.png"),
            lambda data: data["cuts"][0].update(background="never-read.png"),
            lambda data: data["cuts"][0].update(reference_images=["never-read.png"]),
            lambda data: data["cuts"][0].update(reference_ids=["ref_0001"]),
            lambda data: data["cuts"][0].update(controls=[{"image": "never-read.png"}]),
        ]
        for index, mutate in enumerate(mutations):
            data = json.loads(json.dumps(self.data))
            mutate(data)
            self.source.write_text(json.dumps(data), encoding="utf-8")
            destination = self.root / f"rejected-{index}"
            with self.subTest(field=index), patch("src.factory.Image.open") as image_open, \
                    patch("src.factory.load_references") as catalog_read:
                with self.assertRaises(ValueError):
                    prepare_job(self.source, destination)
            image_open.assert_not_called()
            catalog_read.assert_not_called()
            self.assertFalse((destination / "job.json").exists())

    def test_cli_reference_selection_cannot_enable_image_generation(self):
        with patch("src.factory.load_references") as catalog_read:
            with self.assertRaises(ValueError):
                prepare_job(self.source, self.job, reference_ids=["ref_0001"])
        catalog_read.assert_not_called()
        self.assertFalse((self.job / "job.json").exists())

    def test_invalid_image_and_unknown_cut_do_not_corrupt_job(self):
        prepare_job(self.source, self.job)
        original_job = (self.job / "job.json").read_bytes()
        with self.assertRaises(ValueError):
            import_cut(self.job, "missing", self.art)
        bad = self.root / "not_image.png"
        bad.write_bytes(b"not image")
        with self.assertRaises(OSError):
            import_cut(self.job, "cut_001", bad)
        self.assertEqual((self.job / "job.json").read_bytes(), original_job)

    def test_existing_job_and_nonportable_cut_ids_rejected(self):
        prepare_job(self.source, self.job)
        with self.assertRaises(FileExistsError):
            prepare_job(self.source, self.job)
        self.data["cuts"][0]["id"] = "CON"
        self.source.write_text(json.dumps(self.data), encoding="utf-8")
        with self.assertRaises(ValueError):
            prepare_job(self.source, self.root / "bad")

    def test_cut_id_with_version_suffix_does_not_block_another_cut_revision(self):
        first = dict(self.data["cuts"][0], id="a")
        second = dict(self.data["cuts"][0], id="a_v002")
        self.data["cuts"] = [first, second]
        self.source.write_text(json.dumps(self.data), encoding="utf-8")
        prepare_job(self.source, self.job)
        one = import_cut(self.job, "a", self.art)
        two = import_cut(self.job, "a_v002", self.art)
        revision = import_cut(self.job, "a", self.art, replace=True)
        self.assertEqual(len({one["image"], two["image"], revision["image"]}), 3)
        self.assertTrue(all((self.job / r["image"]).is_file() for r in (one, two, revision)))


if __name__ == "__main__":
    unittest.main()
