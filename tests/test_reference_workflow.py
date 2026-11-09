"""Image-reference rejection and archival readback for text-only production."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from src.factory import prepare_job, import_cut, build_job, job_status
from src.operations import next_action


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class ReferenceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="reference-flow-", dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = self.root / "references/catalog.json"
        original = self.catalog.parent / "ref_0001/original.png"
        original.parent.mkdir(parents=True)
        Image.new("RGB", (64, 96), "#669966").save(original)
        self.original = original
        self.metadata = original.parent / "reference.json"
        save(self.metadata, {"id": "ref_0001", "observations": ["ARCHIVED_VISUAL_GUIDANCE_SENTINEL"]})
        save(self.catalog, {"schema_version": 1, "references": [{
            "id": "ref_0001", "title": "Archived fixture", "original": "ref_0001/original.png",
            "metadata": "ref_0001/reference.json", "sha256": hashlib.sha256(original.read_bytes()).hexdigest()}]})
        self.episode = {"title": "Text-only reference boundary test", "cuts": [
            {"id": "cut_a", "description": "A quiet room", "characters": [], "dialogue": []},
            {"id": "cut_b", "description": "The next view", "characters": [], "dialogue": []}]}
        self.source = self.root / "episode.json"
        save(self.source, self.episode)
        self.job = self.root / "job"
        self.art = self.root / "generated.png"
        Image.new("RGB", (256, 384), "#b4c8ba").save(self.art)

    def prepare(self, **options):
        return prepare_job(self.source, self.job, reference_catalog=self.catalog, **options)

    def import_both(self):
        prompt = self.root / "actual.txt"
        prompt.write_text("A synthetic room generated from text only", encoding="utf-8")
        for identifier in ("cut_a", "cut_b"):
            import_cut(self.job, identifier, self.art, prompt, used_reference_ids=[])

    def record_fixture_review(self):
        path = self.job / "review.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for cut in data["cuts"].values():
            for check in cut["checks"].values():
                check.update(result="pass", note="Synthetic protocol test record; not an art evaluation")
        save(path, data)

    def test_archive_is_preserved_but_never_loaded_into_new_generation_briefs(self):
        paths = (self.original, self.metadata, self.catalog)
        before = {path: path.read_bytes() for path in paths}
        with patch("src.factory.load_references") as reader:
            job = self.prepare()
        reader.assert_not_called()
        self.assertEqual(job["generation_input_mode"], "text_only")
        self.assertEqual(job["generation_policy_version"], "text-only-v1")
        self.assertTrue(all(cut["reference_images"] == [] for cut in job["cuts"]))
        self.assertTrue(all(cut["visual_reference_ids"] == [] for cut in job["cuts"]))
        for cut in job["cuts"]:
            self.assertNotIn("ARCHIVED_VISUAL_GUIDANCE_SENTINEL",
                             (self.job / cut["prompt_file"]).read_text(encoding="utf-8"))
        self.assertEqual(before, {path: path.read_bytes() for path in paths})
        self.assertEqual(job_status(self.job)["visual_references"]["status"], "not_selected")

    def test_global_cut_and_cli_visual_selection_are_all_rejected(self):
        for location in ("episode", "cut", "cli"):
            data = json.loads(json.dumps(self.episode))
            options = {}
            if location == "episode":
                data["reference_ids"] = ["ref_0001"]
            elif location == "cut":
                data["cuts"][0]["reference_ids"] = ["ref_0001"]
            else:
                options["reference_ids"] = ["ref_0001"]
            save(self.source, data)
            with self.subTest(location=location), patch("src.factory.load_references") as reader:
                with self.assertRaises(ValueError):
                    self.prepare(**options)
            reader.assert_not_called()
            self.assertFalse((self.job / "job.json").exists())

    def test_explicit_empty_reference_lists_are_allowed_without_a_catalog(self):
        self.episode["reference_ids"] = []
        self.episode["cuts"][0]["reference_ids"] = []
        save(self.source, self.episode)
        self.catalog.write_text("not valid JSON and must not be read", encoding="utf-8")
        job = self.prepare(reference_ids=[])
        self.assertTrue(all(not cut["reference_images"] for cut in job["cuts"]))
        self.assertEqual(job_status(self.job)["visual_references"]["status"], "not_selected")

    def test_reference_use_cannot_be_declared_on_a_text_only_import(self):
        self.prepare()
        before = (self.job / "job.json").read_bytes()
        with patch("src.factory.Image.open") as image_open:
            with self.assertRaises(ValueError):
                import_cut(self.job, "cut_a", self.art, used_reference_ids=["ref_0001"])
        image_open.assert_not_called()
        self.assertEqual((self.job / "job.json").read_bytes(), before)
        first = import_cut(self.job, "cut_a", self.art, used_reference_ids=[])
        second = import_cut(self.job, "cut_b", self.art)
        self.assertEqual(first["visual_reference_usage"], {"status": "declared", "ids": []})
        self.assertEqual(second["visual_reference_usage"], {"status": "not_recorded", "ids": None})
        self.assertEqual(first["generation_input_mode"], "text_only")

    def test_changed_archived_library_does_not_become_a_generation_dependency(self):
        self.prepare()
        self.original.write_bytes(b"archived material changed outside generation")
        self.catalog.write_text("archived catalog is unavailable", encoding="utf-8")
        with patch("src.legal_qa.legal_status", return_value={"status": "passed"}):
            action = next_action(self.job)
        self.assertEqual(action["action"], "generate")
        self.assertNotIn("referenced_image_paths", action["imagegen"])
        self.assertNotIn("num_last_images_to_include", action["imagegen"])

    def test_legacy_job_and_output_remain_readable_without_relabeling_history(self):
        self.prepare()
        self.import_both()
        build_job(self.job)
        self.record_fixture_review()
        path = self.job / "job.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("generation_input_mode")
        data.pop("generation_policy_version")
        data["cuts"][0]["imported"].pop("generation_input_mode", None)
        save(path, data)
        before = {file: file.read_bytes() for file in self.job.rglob("*") if file.is_file()}
        status = job_status(self.job)
        self.assertTrue(status["output_valid"])
        self.assertEqual(status["approval"], "not_reviewed")
        for cut_id in (None, "cut_a"):
            with self.assertRaises(ValueError):
                next_action(self.job, cut_id)
        with self.assertRaises(ValueError):
            import_cut(self.job, "cut_b", self.art, replace=True)
        self.assertEqual(before, {file: file.read_bytes() for file in self.job.rglob("*") if file.is_file()})

    def test_image_revision_dialogue_and_output_changes_invalidate_recorded_review(self):
        self.prepare()
        self.import_both()
        build_job(self.job)
        self.record_fixture_review()
        self.assertEqual(job_status(self.job)["reference_review"]["status"], "passed")
        conti_path = self.job / "conti/episode.json"
        conti = json.loads(conti_path.read_text(encoding="utf-8"))
        conti["cuts"][0]["gap_after"] = 200
        save(conti_path, conti)
        self.assertEqual(job_status(self.job)["reference_review"]["status"], "stale")
        build_job(self.job, overwrite=True)
        self.assertEqual(job_status(self.job)["reference_review"]["status"], "not_reviewed")
        self.record_fixture_review()
        import_cut(self.job, "cut_a", self.art, replace=True)
        self.assertEqual(job_status(self.job)["reference_review"]["status"], "not_reviewed")
        record = json.loads((self.job / "job.json").read_text(encoding="utf-8"))["cuts"][0]
        self.assertEqual(record["history"][-1]["visual_review"]["checks"]["composition"]["result"], "pass")


if __name__ == "__main__":
    unittest.main()
