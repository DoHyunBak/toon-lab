"""Portable synthetic layout -> notice integration, with no model/API calls.

The workflow adoption is real control-flow validation of synthetic evidence,
not a claim of legal clearance or human art approval. An installed local font
is copied into the temporary fixture only; no font or artwork is bundled.
"""

import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from src.ai_notice import package_review
from src.bubble_renderer import _load_font
from src.factory import import_cut, job_status, prepare_job
from src.workflow_policy import VERSION, adopt_workflow
from tools.build_layout_job import build_layout_job


REPO = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PortableLayoutDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="portable-layout-", dir=REPO)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.job = self.root / "job"
        self.output = self.root / "assembly"
        self.layout = self.root / "layout.json"
        self.notice = self.root / "notice.json"
        # Read the public configuration before narrowing notice's owned root.
        notice = read(REPO / "docs/public/templates/notice.example.json")
        loaded = _load_font(None, 28, "제작 검토 안내")
        self.font = self.root / ("local-font" + Path(loaded.path).suffix)
        shutil.copyfile(loaded.path, self.font)
        notice.update(font=self.font.name, font_bold=self.font.name)
        save(self.notice, notice)

        manuscript = self.root / "manuscript.json"
        save(manuscript, {"title": "Synthetic portable fixture", "cuts": [
            {"id": "scene", "description": "A synthetic four-color rectangle", "characters": [], "dialogue": []}]})
        prepare_job(manuscript, self.job)
        evidence = self.root / "evidence.md"
        evidence.write_text("Synthetic fixture authorization only; no external processing or real art approval.", encoding="utf-8")
        policy = self.root / "policy.json"
        save(policy, {"version": VERSION, "legal_review_trigger": "workflow_changes_or_rights_reports",
                      "reviewer": "Synthetic control-flow test", "rights_basis": "Locally drawn test pixels",
                      "license_conditions": "No external artwork; local font used only in this temporary test",
                      "permitted_external_processing": "None", "review_scope": "Synthetic pipeline test only",
                      "holds": [], "evidence": [{"path": str(evidence), "sha256": digest(evidence)}]})
        self.assertEqual(adopt_workflow(self.job, policy)["status"], "reviewed")

        art = self.root / "synthetic.png"
        pixels = Image.new("RGB", (800, 400), "#314e68")
        for color, box in [("red", (0, 0, 50, 50)), ("green", (750, 0, 800, 50)),
                           ("blue", (0, 350, 50, 400)), ("yellow", (750, 350, 800, 400))]:
            pixels.paste(color, box)
        pixels.save(art)
        imported = import_cut(self.job, "scene", art, self.job / "prompts/scene.txt", used_reference_ids=[])
        self.raw = self.job / imported["image"]
        self.data = {"expected_ids": ["scene"], "panels": [
            {"id": "scene", "role": "wide", "time_layer": "present", "link_after": "ending",
             "render_size": [1024, 1536], "source_image": str(self.raw), "source_width": 800,
             "source_height": 400, "description": "A synthetic four-color rectangle", "dialogue": [],
             "old_geometry": {"x": 0, "top": 0, "art_width": 800, "art_height": 400, "canvas_height": 400}}]}
        save(self.layout, self.data)

    def build(self):
        return build_layout_job(self.job, self.layout, self.output, self.font)

    def package(self, source, output):
        with patch("src.ai_notice.ROOT", self.root):
            return package_review(source, output, notice=self.notice)

    def test_layout_then_notice_preserves_full_art_body_and_pending_reviews(self):
        prior_review = read(self.job / "review.json")
        first_check = next(iter(prior_review["cuts"]["scene"]["checks"].values()))
        first_check.update(result="pass", note="Synthetic old check; must reset for a new assembly")
        save(self.job / "review.json", prior_review)
        raw_before = self.raw.read_bytes()
        source = self.build()
        state = job_status(self.job)
        current = read(self.job / "job.json")
        review = read(self.job / "review.json")
        self.assertTrue(state["output_valid"])
        self.assertEqual(state["output"]["assembly_mode"], "semantic_layout_with_measured_lettering")
        self.assertEqual(state["approval"], "not_reviewed")
        self.assertNotEqual(state["reference_review"]["status"], "passed")
        self.assertTrue(all(check["result"] == "not_reviewed" for check in review["cuts"]["scene"]["checks"].values()))
        self.assertEqual(review["output_manifest_sha256"], digest(source))
        self.assertEqual(review["episode_sha256"], digest(self.job / current["episode"]))
        self.assertEqual(review["cuts"]["scene"]["image_sha256"], digest(self.raw))
        provenance = read(self.output / "layout_provenance.json")[0]
        self.assertEqual(provenance["sha256"], digest(self.raw))
        self.assertIn("full_source_preserved", provenance["decision"]["reason"])
        with Image.open(self.raw) as raw, Image.open(self.output / "art/scene.png") as composed:
            self.assertEqual(raw.size, composed.size)
            self.assertEqual(raw.convert("RGB").tobytes(), composed.convert("RGB").tobytes())

        source_before = source.read_bytes()
        delivery = self.root / "notice-candidate"
        result = self.package(source, delivery)
        manifest = read(delivery / "manifest.json")
        body_name = read(source)["full"]["path"]
        with Image.open(self.output / body_name) as body, Image.open(delivery / "full_strip.png") as full:
            preserved = full.crop((0, manifest["body_offset_y"], 800, full.height))
            self.assertEqual(preserved.tobytes(), body.convert("RGB").tobytes())
        self.assertEqual(manifest["source_manifest_sha256"], digest(source))
        self.assertTrue(manifest["body_pixels_unchanged"])
        self.assertEqual(result["status"], "internal_review_candidate")
        self.assertFalse(result["release_approved"])
        self.assertEqual(manifest["work_qa_status"], "not_transferred_from_source")
        self.assertIn("new_composite_visual_review_pending", result["blockers"])
        self.assertIn("underlying_work_rights_and_required_qa_not_cleared", result["blockers"])
        self.assertIn("actual_report_channel_not_supplied", result["blockers"])
        self.assertEqual(manifest["notice"]["legal_clearance"], "not_issued")
        self.assertEqual(self.raw.read_bytes(), raw_before)
        self.assertEqual(source.read_bytes(), source_before)
        with self.assertRaisesRegex(ValueError, "already has an AI notice"):
            self.package(delivery / "manifest.json", self.root / "duplicate-notice")
        self.assertFalse((self.root / "duplicate-notice").exists())

    def test_layout_rejects_raw_substitution_story_loss_and_wrong_dimensions(self):
        other = self.root / "other.png"
        Image.new("RGB", (800, 400), "black").save(other)
        substitutions = [
            ("source_image", str(other), "current imported raw"),
            ("description", "A different event", "current manuscript"),
            ("source_width", 799, "source dimensions changed"),
        ]
        for field, value, error in substitutions:
            with self.subTest(field=field):
                data = copy.deepcopy(self.data)
                data["panels"][0][field] = value
                save(self.layout, data)
                with self.assertRaisesRegex(ValueError, error):
                    self.build()
                self.assertFalse(self.output.exists())
        data = copy.deepcopy(self.data)
        data["expected_ids"] = []
        save(self.layout, data)
        with self.assertRaisesRegex(ValueError, "all current scene IDs and order"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_plan_snapshot_and_raw_tampering_are_detected_and_stale_notice_is_rejected(self):
        source = self.build()
        current = read(self.job / "job.json")
        for artifact in [self.output / "layout_plan.json", self.job / current["output"]["assembly_input"]["path"]]:
            original = artifact.read_bytes()
            artifact.write_text("{}", encoding="utf-8")
            self.assertFalse(job_status(self.job)["output_valid"])
            artifact.write_bytes(original)
            self.assertTrue(job_status(self.job)["output_valid"])

        master = self.output / read(source)["full"]["path"]
        Image.new("RGB", (800, 400), "black").save(master)
        with self.assertRaisesRegex(ValueError, "Source master differs"):
            self.package(source, self.root / "stale-notice")
        self.assertFalse((self.root / "stale-notice").exists())
        Image.new("RGB", (800, 400), "black").save(self.raw)
        self.assertEqual(job_status(self.job)["changed"], ["scene"])
        with self.assertRaisesRegex(ValueError, "current raw imports must be intact"):
            build_layout_job(self.job, self.layout, self.root / "invalid-rebuild", self.font)


if __name__ == "__main__":
    unittest.main()
