"""Scoped Jev screening workflow; all model responses here are synthetic fixtures."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from src.factory import _load, build_job, import_cut, prepare_job
from src.plagiarism import plagiarism_status, run_check, submit_plagiarism_review
from src.typesafe_jev import DEFAULT_MODEL


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PlagiarismTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="plagiarism-test-", dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.job = self.root / "job"
        self.source = self.root / "episode.json"
        self.art = self.root / "fixture.png"
        image = Image.new("RGB", (320, 480), "#d4dfcc")
        draw = ImageDraw.Draw(image)
        draw.rectangle((40, 50, 160, 340), fill="#425b70")
        draw.ellipse((170, 200, 290, 320), fill="#a56d43")
        image.save(self.art)
        save(self.source, {"title": "Synthetic screening fixture", "cuts": [
            {"id": "cut_a", "description": "A rectangle beside a circle", "characters": [], "dialogue": []},
            {"id": "cut_b", "description": "The same fixture, not production art", "characters": [], "dialogue": []}]})
        prepare_job(self.source, self.job)
        prompt = self.root / "prompt.txt"
        prompt.write_text("Synthetic fixture provenance only; no generation call.", encoding="utf-8")
        for identifier in ("cut_a", "cut_b"):
            import_cut(self.job, identifier, self.art, prompt, used_reference_ids=[])
        self.output = build_job(self.job)
        self.comparison = self.root / "comparison.png"
        image.transpose(Image.Transpose.FLIP_LEFT_RIGHT).save(self.comparison)
        self.corpus = self.root / "corpus.json"
        self.corpus_data = {
            "schema_version": 1, "scope": "Two synthetic cuts against one owned fixture only",
            "external_processing_allowed": True, "rights_basis": "Locally drawn test shapes",
            "sources": [{"id": "owned_fixture", "image": self.comparison.name,
                         "text": "Synthetic geometric fixture", "rights_basis": "Locally drawn test shapes"}]}
        save(self.corpus, self.corpus_data)
        self.check_file = self.job / "plagiarism_check.json"

    def status(self):
        root, job = _load(self.job)
        return plagiarism_status(root, job)

    def response(self, relation="no_similarity"):
        def answer(state, questions, assets, *, model=DEFAULT_MODEL, **kwargs):
            answers = {}
            for key, question in questions.items():
                options = question["criteria"]
                selected = relation if relation in options else "none" if "none" in options else next(iter(options))
                answers[key] = {"type": "choice", "choice": selected, "confidence": 1.0,
                                "probabilities": {option: float(option == selected) for option in options}}
            return {"model": model, "answers": answers, "usage": {"input_tokens": 1, "output_tokens": 1}}
        return answer

    def screen(self, relation="no_similarity", **kwargs):
        with patch("src.plagiarism.ask", side_effect=self.response(relation)) as transport:
            result = run_check(self.job, self.corpus, **kwargs)
        return result, transport.call_count

    def review(self):
        check = read(self.check_file)
        path = self.root / "observed-plagiarism-review.json"
        value = {"check_sha256": digest(self.check_file), "reviewer": "Synthetic test reviewer",
                 "decision": "accept", "notes": "Workflow fixture only, not a legal or visual finding",
                 "pair_reviews": {key: {"decision": "accept", "note": "Synthetic pair review fixture"}
                                  for key in check["pairs"]}}
        save(path, value)
        return path, value

    def test_no_record_is_not_checked_and_read_only(self):
        before = (self.job / "job.json").read_bytes()
        self.assertEqual(self.status()["status"], "not_checked")
        self.assertFalse(self.check_file.exists())
        self.assertEqual((self.job / "job.json").read_bytes(), before)

    def test_empty_or_unauthorized_corpus_never_calls_api(self):
        for field, value in (("sources", []), ("external_processing_allowed", False), ("rights_basis", ""),
                             ("rights_basis", None), ("scope", None), ("scope", 42)):
            with self.subTest(field=field):
                data = json.loads(json.dumps(self.corpus_data))
                data[field] = value
                save(self.corpus, data)
                with patch("src.plagiarism.ask") as transport:
                    with self.assertRaises(ValueError):
                        run_check(self.job, self.corpus)
                transport.assert_not_called()
                self.assertNotEqual(self.status()["status"], "passed")

    def test_comparison_source_requires_explicit_rights_and_well_formed_records(self):
        for source in (None, "not an object", {"id": "owned_fixture", "image": self.comparison.name},
                       {"id": "owned_fixture", "image": self.comparison.name, "rights_basis": None}):
            with self.subTest(source=source):
                data = json.loads(json.dumps(self.corpus_data))
                data["sources"] = [source]
                save(self.corpus, data)
                with patch("src.plagiarism.ask") as transport:
                    with self.assertRaises(ValueError):
                        run_check(self.job, self.corpus)
                transport.assert_not_called()

    def test_animated_comparison_is_rejected_before_any_api_request(self):
        animated = self.root / "animated-comparison.gif"
        first = Image.new("RGB", (320, 480), "#425b70")
        second = Image.new("RGB", (320, 480), "#a56d43")
        first.save(animated, save_all=True, append_images=[second], duration=100, loop=0)
        data = json.loads(json.dumps(self.corpus_data))
        data["sources"][0]["image"] = animated.name
        save(self.corpus, data)
        with patch("src.plagiarism.ask") as transport:
            with self.assertRaises(ValueError):
                run_check(self.job, self.corpus)
        transport.assert_not_called()
        self.assertEqual(self.status()["status"], "not_checked")

    def test_screen_records_all_pairs_and_keeps_existing_job_and_visual_review_bytes(self):
        original_job = (self.job / "job.json").read_bytes()
        original_review = (self.job / "review.json").read_bytes()
        result, calls = self.screen()
        self.assertEqual(calls, 2)
        self.assertEqual(result["status"], "screened")
        self.assertEqual(self.status()["status"], "screened")
        check = read(self.check_file)
        self.assertEqual(set(check["pairs"]), {"cut_a::owned_fixture", "cut_b::owned_fixture"})
        self.assertTrue(check["complete"])
        self.assertEqual(check["snapshot"]["model"], DEFAULT_MODEL)
        self.assertEqual((self.job / "job.json").read_bytes(), original_job)
        self.assertEqual((self.job / "review.json").read_bytes(), original_review)
        self.assertTrue((self.job / "plagiarism_review.template.json").is_file())

    def test_distinctive_or_uncertain_signal_requires_observed_review(self):
        for relation in ("distinctive_similarity", "uncertain"):
            with self.subTest(relation=relation):
                if self.check_file.exists():
                    self.check_file.unlink()
                result, _ = self.screen(relation)
                self.assertEqual(result["status"], "needs_human_review")
                self.assertNotEqual(self.status()["status"], "passed")

    def test_zero_confidence_or_tied_distribution_is_uncertain_even_with_no_similarity_choice(self):
        for mode in ("zero_confidence", "tied", "zero_and_tied"):
            with self.subTest(mode=mode):
                if self.check_file.exists():
                    self.check_file.unlink()
                response = self.response()
                def uncertain(state, questions, assets, **kwargs):
                    value = response(state, questions, assets, **kwargs)
                    relation = value["answers"]["relation"]
                    if mode != "tied":
                        relation["confidence"] = 0.0
                    if mode != "zero_confidence":
                        relation["probabilities"] = {option: 0.25 for option in relation["probabilities"]}
                    return value
                with patch("src.plagiarism.ask", side_effect=uncertain):
                    result = run_check(self.job, self.corpus)
                self.assertEqual(result["status"], "needs_human_review")
                expected = {"cut_a::owned_fixture", "cut_b::owned_fixture"}
                self.assertEqual(set(result["uncertain_pairs"]), expected)
                self.assertEqual(set(result["flagged_pairs"]), expected)

    def test_request_budget_leaves_incomplete_blocked_and_resume_only_calls_missing_pair(self):
        partial, calls = self.screen(max_requests=1)
        self.assertEqual(calls, 1)
        self.assertNotEqual(partial["status"], "passed")
        self.assertFalse(read(self.check_file)["complete"])
        complete, calls = self.screen(max_requests=1)
        self.assertEqual(calls, 1)
        self.assertEqual(complete["status"], "screened")
        _, calls = self.screen()
        self.assertEqual(calls, 0)

    def test_service_failure_cannot_be_manually_accepted(self):
        with patch("src.plagiarism.ask", side_effect=ValueError("TypeSafe HTTP 503")):
            result = run_check(self.job, self.corpus)
        self.assertEqual(result["status"], "error")
        report, _ = self.review()
        with self.assertRaises(ValueError):
            submit_plagiarism_review(self.job, report)
        self.assertNotEqual(self.status()["status"], "passed")

    def test_invalid_model_or_typed_response_is_recorded_as_error(self):
        for mutation in ("model", "missing_answer", "invalid_choice_probability"):
            with self.subTest(mutation=mutation):
                if self.check_file.exists():
                    self.check_file.unlink()
                response = self.response()
                def invalid(state, questions, assets, **kwargs):
                    value = response(state, questions, assets, **kwargs)
                    if mutation == "model":
                        value["model"] = "unexpected-model"
                    elif mutation == "missing_answer":
                        del value["answers"]["relation"]
                    else:
                        value["answers"]["relation"]["confidence"] = float("nan")
                    return value
                with patch("src.plagiarism.ask", side_effect=invalid):
                    result = run_check(self.job, self.corpus)
                self.assertEqual(result["status"], "error")
                self.assertFalse(read(self.check_file)["complete"])

    def test_deleted_pair_cannot_be_hidden_by_complete_flag_or_manual_acceptance(self):
        self.screen()
        data = read(self.check_file)
        del data["pairs"]["cut_a::owned_fixture"]
        data["complete"] = True
        save(self.check_file, data)
        self.assertNotEqual(self.status()["status"], "passed")
        report, _ = self.review()
        with self.assertRaises(ValueError):
            submit_plagiarism_review(self.job, report)

    def test_long_image_tile_coverage_is_complete_and_tampered_geometry_cannot_be_accepted(self):
        image = Image.new("RGB", (320, 1600), "#d4dfcc")
        draw = ImageDraw.Draw(image)
        for top, color in ((0, "#425b70"), (640, "#a56d43"), (1280, "#478165")):
            draw.rectangle((40, top + 20, 280, min(top + 280, 1599)), fill=color)
        image.save(self.comparison)
        self.assertEqual(self.screen()[0]["status"], "screened")
        check = read(self.check_file)
        expected_boxes = [[0, 0, 320, 640], [0, 640, 320, 1280], [0, 1280, 320, 1600]]
        for pair in check["pairs"].values():
            self.assertEqual(pair["source_boxes"], expected_boxes)
            self.assertEqual(pair["tile_counts"], [1, 3])
        report, _ = self.review()
        self.assertEqual(submit_plagiarism_review(self.job, report)["status"], "passed")
        original = self.check_file.read_bytes()
        for mutation in ("missing_target", "missing_source", "wrong_target", "wrong_source", "missing_tile"):
            with self.subTest(mutation=mutation):
                changed = json.loads(json.dumps(check))
                pair = changed["pairs"]["cut_a::owned_fixture"]
                if mutation == "missing_target":
                    del pair["target_boxes"]
                elif mutation == "missing_source":
                    del pair["source_boxes"]
                elif mutation == "wrong_target":
                    pair["target_boxes"][0][2] -= 1
                elif mutation == "wrong_source":
                    pair["source_boxes"][1][1] += 1
                else:
                    pair["source_boxes"].pop()
                save(self.check_file, changed)
                self.assertEqual(self.status()["status"], "stale")
                current_report, _ = self.review()
                with self.assertRaises(ValueError):
                    submit_plagiarism_review(self.job, current_report)
                self.check_file.write_bytes(original)
                self.assertEqual(self.status()["status"], "passed")

    def test_observed_review_requires_all_current_pairs_then_passes_scoped_gate(self):
        self.screen()
        report, value = self.review()
        for mutation in ("missing_pair", "missing_note", "missing_reviewer", "stale_hash"):
            with self.subTest(mutation=mutation):
                changed = json.loads(json.dumps(value))
                if mutation == "missing_pair":
                    del changed["pair_reviews"]["cut_a::owned_fixture"]
                elif mutation == "missing_note":
                    changed["pair_reviews"]["cut_a::owned_fixture"]["note"] = ""
                elif mutation == "missing_reviewer":
                    changed["reviewer"] = ""
                else:
                    changed["check_sha256"] = "0" * 64
                save(report, changed)
                with self.assertRaises(ValueError):
                    submit_plagiarism_review(self.job, report)
                self.assertNotEqual(self.status()["status"], "passed")
        save(report, value)
        self.assertEqual(submit_plagiarism_review(self.job, report)["status"], "passed")
        self.assertEqual(self.status()["status"], "passed")

    def test_observed_needs_fix_decision_blocks_scoped_gate(self):
        self.screen()
        report, value = self.review()
        value["decision"] = "needs_fix"
        value["pair_reviews"]["cut_a::owned_fixture"]["decision"] = "needs_fix"
        save(report, value)
        self.assertEqual(submit_plagiarism_review(self.job, report)["status"], "needs_human_review")
        self.assertNotEqual(self.status()["status"], "passed")

    def test_changed_bound_artifacts_and_corpus_make_accepted_report_stale(self):
        self.screen()
        report, _ = self.review()
        submit_plagiarism_review(self.job, report)
        job = read(self.job / "job.json")
        manifest = read(self.output)
        paths = [self.job / job["episode"], self.job / job["cuts"][0]["imported"]["image"],
                 self.job / job["cuts"][0]["imported"]["original"], self.output,
                 self.output.parent / manifest["full"]["path"], self.corpus, self.comparison]
        for path in paths:
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(original + b"\nchanged after screening")
                self.assertNotEqual(self.status()["status"], "passed")
                with self.assertRaises(ValueError):
                    submit_plagiarism_review(self.job, report)
                path.write_bytes(original)
                self.assertEqual(self.status()["status"], "passed")

    def test_input_change_during_api_call_does_not_produce_current_screen(self):
        response = self.response()
        def mutate(state, questions, assets, **kwargs):
            self.comparison.write_bytes(self.comparison.read_bytes() + b"changed during request")
            return response(state, questions, assets, **kwargs)
        with patch("src.plagiarism.ask", side_effect=mutate):
            try:
                run_check(self.job, self.corpus)
            except ValueError:
                pass
        self.assertNotIn(self.status()["status"], ("screened", "passed"))


if __name__ == "__main__":
    unittest.main()
