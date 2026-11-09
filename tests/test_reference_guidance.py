"""Reference identity, source preservation and explicit image-bound review."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from src.reference_guidance import CRITERIA, guidance_text, load_references, make_review, review_summary


class ReferenceGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="reference-tests-", dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        folder = self.root / "ref_0001"
        folder.mkdir()
        self.original = folder / "original.png"
        Image.new("RGB", (24, 40), "#ab9876").save(self.original)
        self.sha = hashlib.sha256(self.original.read_bytes()).hexdigest()
        self.metadata_path = folder / "reference.json"
        self.metadata = {"id": "ref_0001", "title": "연출 예시", "category": "genre_comparison_board",
                         "original": {"path": "original.png", "format": "PNG", "width": 24, "height": 40,
                                      "bytes": self.original.stat().st_size, "sha256": self.sha},
                         "observations": [{"topic": "완급", "note": "준비의 작은 컷 뒤에 큰 동작 컷을 둔다."}],
                         "production_application": {"layout": "비교판은 장르를 선택해 참고한다."}}
        self.catalog_path = self.root / "catalog.json"
        self.catalog = {"schema_version": 1, "references": [
            {"id": "ref_0001", "title": "연출 예시", "original": "ref_0001/original.png",
             "metadata": "ref_0001/reference.json", "sha256": self.sha, "tags": ["완급"]}]}
        self.write(self.metadata_path, self.metadata)
        self.write(self.catalog_path, self.catalog)
        self.review_path = self.root / "review.json"
        self.cuts = [{"id": "cut_001", "visual_reference_ids": ["ref_0001"]}]
        self.expected_refs = {"cut_001": ["ref_0001"]}

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def summary(self, image_hash=None):
        return review_summary(self.review_path, {"cut_001": image_hash}, self.expected_refs)

    def recorded_review(self, result="pass"):
        review = make_review(self.cuts)
        review["cuts"]["cut_001"]["image_sha256"] = self.sha
        for key, check in review["cuts"]["cut_001"]["checks"].items():
            check.update(result=result, note=f"{CRITERIA[key]} 원고와 현재 이미지를 비교해 기록함.")
        self.write(self.review_path, review)
        return review

    def test_selected_reference_integrity_and_original_sources_preserved(self):
        before = {p: p.read_bytes() for p in (self.original, self.catalog_path, self.metadata_path)}
        references = load_references(self.catalog_path, ["ref_0001"])
        self.assertEqual(references[0]["path"], str(self.original))
        self.assertEqual(references[0]["metadata_path"], str(self.metadata_path))
        self.assertEqual(references[0]["metadata_sha256"], hashlib.sha256(self.metadata_path.read_bytes()).hexdigest())
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        text = guidance_text(references, "주인공의 준비 동작")
        self.assertIn("준비의 작은 컷", text)
        self.assertIn("주인공의 준비 동작", text)
        self.assertIn("별도로 전달", text)
        self.assertIn("이야기·인물·대사를 복사하지", text)

    def test_unknown_duplicate_and_unsafe_ids_rejected(self):
        for identifiers in (["ref_0099"], ["ref_0001", "ref_0001"], ["../ref_0001"], "ref_0001"):
            with self.subTest(ids=identifiers), self.assertRaises(ValueError):
                load_references(self.catalog_path, identifiers)

    def test_unselected_missing_files_are_not_loaded(self):
        self.catalog["references"].append({"id": "ref_0002", "original": "missing.png", "metadata": "missing.json"})
        self.write(self.catalog_path, self.catalog)
        self.assertEqual(len(load_references(self.catalog_path, ["ref_0001"])), 1)

    def test_catalog_and_metadata_cannot_escape_reference_root(self):
        for field in ("original", "metadata"):
            saved = self.catalog["references"][0][field]
            self.catalog["references"][0][field] = "../outside.png"
            self.write(self.catalog_path, self.catalog)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "Unsafe"):
                load_references(self.catalog_path, ["ref_0001"])
            self.catalog["references"][0][field] = saved

    def test_missing_and_changed_original_detected(self):
        self.original.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "digest"):
            load_references(self.catalog_path, ["ref_0001"])
        self.original.unlink()
        with self.assertRaisesRegex(ValueError, "Missing"):
            load_references(self.catalog_path, ["ref_0001"])

    def test_image_actual_dimensions_and_format_are_checked(self):
        self.metadata["original"]["width"] = 99
        self.write(self.metadata_path, self.metadata)
        with self.assertRaisesRegex(ValueError, "dimensions"):
            load_references(self.catalog_path, ["ref_0001"])

    def test_metadata_identity_and_optional_digest_checked(self):
        self.catalog["references"][0]["metadata_sha256"] = "0" * 64
        self.write(self.catalog_path, self.catalog)
        with self.assertRaisesRegex(ValueError, "digest"):
            load_references(self.catalog_path, ["ref_0001"])
        self.catalog["references"][0].pop("metadata_sha256")
        self.write(self.catalog_path, self.catalog)
        self.metadata["id"] = "ref_0002"
        self.write(self.metadata_path, self.metadata)
        with self.assertRaisesRegex(ValueError, "identity"):
            load_references(self.catalog_path, ["ref_0001"])

    def test_invalid_catalog_structure_is_actionable(self):
        self.write(self.catalog_path, [])
        with self.assertRaisesRegex(ValueError, "catalog"):
            load_references(self.catalog_path, [])

    def test_default_and_missing_review_never_pass(self):
        self.assertEqual(self.summary()["status"], "not_configured")
        self.write(self.review_path, make_review(self.cuts))
        summary = self.summary()
        self.assertEqual(summary["status"], "not_reviewed")
        self.assertEqual(summary["counts"]["not_reviewed"], 7)
        self.assertEqual(set(CRITERIA), set(make_review(self.cuts)["cuts"]["cut_001"]["checks"]))
        self.assertEqual(make_review(self.cuts)["criteria"], CRITERIA)

    def test_recorded_notes_and_matching_hashes_required_for_passed(self):
        review = self.recorded_review()
        self.assertEqual(self.summary(self.sha)["status"], "passed")
        review["cuts"]["cut_001"]["checks"]["performance"]["note"] = " "
        self.write(self.review_path, review)
        with self.assertRaisesRegex(ValueError, "note"):
            self.summary(self.sha)

    def test_image_revision_and_changed_reference_ids_make_review_stale(self):
        self.recorded_review()
        self.assertEqual(self.summary("b" * 64)["status"], "stale")
        self.expected_refs["cut_001"] = ["ref_0002"]
        self.assertEqual(self.summary(self.sha)["status"], "stale")

    def test_fix_and_pending_results_are_not_passed(self):
        review = self.recorded_review()
        check = review["cuts"]["cut_001"]["checks"]["lettering"]
        check.update(result="needs_fix", note="말풍선이 눈을 가림.")
        self.write(self.review_path, review)
        self.assertEqual(self.summary(self.sha)["status"], "needs_fix")
        check.update(result="not_reviewed", note="")
        self.write(self.review_path, review)
        self.assertEqual(self.summary(self.sha)["status"], "not_reviewed")

    def test_no_image_and_no_expected_cuts_never_pass(self):
        self.recorded_review()
        self.assertNotEqual(self.summary()["status"], "passed")
        self.write(self.review_path, {"schema_version": 1, "cuts": {}})
        self.assertEqual(review_summary(self.review_path, {}, {})["status"], "not_reviewed")

    def test_unknown_result_missing_checks_and_bad_json_are_actionable(self):
        review = self.recorded_review()
        review["cuts"]["cut_001"]["checks"]["pacing"]["result"] = "auto_pass"
        self.write(self.review_path, review)
        with self.assertRaisesRegex(ValueError, "result"):
            self.summary(self.sha)
        review["cuts"]["cut_001"]["checks"].pop("pacing")
        self.write(self.review_path, review)
        with self.assertRaisesRegex(ValueError, "seven"):
            self.summary(self.sha)
        self.review_path.write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "JSON"):
            self.summary(self.sha)
