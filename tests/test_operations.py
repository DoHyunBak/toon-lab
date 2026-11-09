"""Executable agent handoff and image-bound review workflow, using fixture art."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from src.factory import prepare_job, import_cut, build_job, job_status
from src.operations import _provenance, next_action, submit_review


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class OperationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="operations-test-", dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.job = self.root / "job"
        self.source = self.root / "episode.json"
        self.art = self.image("generated-fixture.png", "#9eaeb3")
        characters = self.root / "characters.json"
        save(characters, {"characters": {"min": {
            "description": "adult, short dark hair, green jacket", "reference_images": []}}})
        save(self.source, {"title": "Operator fixture, not production art", "cuts": [
            {"id": "cut_a", "description": "Min stands at the doorway", "characters": ["min"],
             "dialogue": [{"speaker": "min", "text": "여기가 웹툰 공장이구나.", "position": "top-left"}]},
            {"id": "cut_b", "description": "Min looks into the same room", "characters": ["min"],
             "dialogue": [{"speaker": "min", "text": "준비됐어.", "position": "top-left"}]}]})
        prepare_job(self.source, self.job, characters)
        # These image handoff fixtures isolate the existing visual workflow.
        # Legal QA routing and evidence validation have separate coverage below.
        self.legal = patch("src.legal_qa.legal_status", return_value={"status": "passed"})
        self.legal.start()
        self.addCleanup(self.legal.stop)

    def image(self, relative, color):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 96), color).save(path)
        return path

    def import_current(self, identifier, replace=False):
        action = next_action(self.job, identifier)
        prompt = self.root / f"{identifier}-actual-prompt.txt"
        prompt.write_text(action["imagegen"]["prompt"], encoding="utf-8")
        return import_cut(self.job, identifier, self.art, prompt, replace,
                          used_reference_ids=action["used_reference_ids"])

    def test_old_provider_records_are_preserved_and_never_accepted_as_ready(self):
        self.import_current('cut_a')
        self.import_current('cut_b')
        path = self.job / 'job.json'
        job = json.loads(path.read_text(encoding='utf-8'))
        job['cuts'][0]['imported']['provider'] = 'retired-backend'
        save(path, job)
        before = path.read_bytes()
        issues = _provenance(job, self.job)
        self.assertTrue(any('unsupported generation provider' in issue for issue in issues))
        self.assertEqual(next_action(self.job)['action'], 'record_provenance')
        self.assertEqual(path.read_bytes(), before)

    def test_replan_blocks_both_explicit_and_automatic_generation(self):
        save(self.job/'generation_evidence/cut_a.replan.json',
             {'prompt_sha256':'unresolved'})
        self.assertEqual(next_action(self.job,'cut_a')['action'],'replan')
        self.assertEqual(next_action(self.job)['action'],'replan')

    def test_sequence_defect_blocks_explicit_automatic_and_completed_job(self):
        job = json.loads((self.job/'job.json').read_text(encoding='utf-8'))
        ledger = dict(episode_sha256=digest(self.job/job['episode']), defects=[dict(
            id='shared-room',affected_cuts=['cut_a','cut_b'],symptom='Room changed',
            cause='Wrong shared setting',status='open')])
        save(self.job/'sequence_defects.json',ledger)
        self.assertEqual(next_action(self.job,'cut_b')['action'],'resolve_sequence_defect')
        self.assertEqual(next_action(self.job)['action'],'resolve_sequence_defect')
        (self.job/'sequence_defects.json').unlink()
        self.import_all()
        save(self.job/'sequence_defects.json',ledger)
        self.assertEqual(next_action(self.job)['action'],'resolve_sequence_defect')

    def import_all(self):
        for identifier in ("cut_a", "cut_b"):
            self.import_current(identifier)

    def report(self, result="pass"):
        review = json.loads((self.job / "review.json").read_text(encoding="utf-8"))
        for cut in review["cuts"].values():
            for check in cut["checks"].values():
                check.update(result=result, note="Synthetic workflow fixture observation; not an art evaluation")
        path = self.root / "observed-review.json"
        save(path, review)
        return path, review

    def test_generation_payload_is_text_only_and_keeps_current_scene_identity(self):
        action = next_action(self.job)
        self.assertEqual((action["action"], action["cut_id"], action["replace"]), ("generate", "cut_a", False))
        self.assertEqual(action["used_reference_ids"], [])
        payload = action["imagegen"]
        self.assertFalse(payload["transparent_background"])
        self.assertNotIn("referenced_image_paths", payload)
        self.assertNotIn("num_last_images_to_include", payload)
        self.assertEqual(set(payload), {"prompt", "transparent_background"})
        for expected in ("1024 x 1536", "short dark hair", "green jacket", "Min stands at the doorway"):
            self.assertIn(expected, payload["prompt"])
        self.assertNotIn("Reference image", payload["prompt"])
        job = json.loads((self.job / "job.json").read_text(encoding="utf-8"))
        self.assertEqual(job["generation_input_mode"], "text_only")
        self.assertTrue(all(not record["reference_images"] for record in job["cuts"]))

    def test_unchecked_legal_preflight_blocks_generation_and_explicit_cut(self):
        self.legal.stop()
        before = (self.job / "job.json").read_bytes()
        for cut_id in (None, "cut_a"):
            with self.subTest(cut_id=cut_id), patch("src.legal_qa.ask") as network:
                action = next_action(self.job, cut_id)
            self.assertEqual(action["action"], "legal_check")
            self.assertEqual(action["stage"], "preflight")
            self.assertEqual(action["legal_qa"]["status"], "not_checked")
            self.assertNotIn("imagegen", action)
            network.assert_not_called()
        self.assertEqual((self.job / "job.json").read_bytes(), before)

    def test_each_nonpassed_legal_state_blocks_preflight(self):
        for state in ("not_checked", "stale", "error", "blocked", "screened"):
            with self.subTest(state=state), patch("src.legal_qa.legal_status", return_value={"status": state}):
                action = next_action(self.job, "cut_a")
            self.assertEqual(action["action"], "legal_review" if state == "screened" else "legal_check")
            self.assertEqual(action["stage"], "preflight")
            self.assertNotIn("imagegen", action)
            self.assertIn("--stage preflight", action["command"])

    def test_final_legal_qa_required_before_ready(self):
        self.import_all()
        build_job(self.job)
        path, _ = self.report()
        submit_review(self.job, path)
        def stage_status(root, job, stage="preflight"):
            return {"status": "passed" if stage == "preflight" else "screened"}
        with patch("src.operations.plagiarism_status", return_value={"status": "passed"}), \
                patch("src.legal_qa.legal_status", side_effect=stage_status):
            action = next_action(self.job)
        self.assertEqual(action["action"], "legal_review")
        self.assertEqual(action["stage"], "final")
        self.assertIn("--stage final", action["command"])

    def test_previous_generated_art_is_never_reused_as_generation_input(self):
        imported = self.import_current("cut_a")
        action = next_action(self.job)
        self.assertEqual(action["cut_id"], "cut_b")
        payload = action["imagegen"]
        self.assertNotIn("referenced_image_paths", payload)
        self.assertNotIn("num_last_images_to_include", payload)
        self.assertNotIn(str((self.job / imported["image"]).resolve()), payload["prompt"])
        self.assertNotIn("previous cut continuity", payload["prompt"])
        self.assertIn("Min looks into the same room", payload["prompt"])

    def test_strip_handoff_preserves_panel_layout_instead_of_forcing_portrait_panel(self):
        path = self.job / 'conti/episode.json'
        episode = json.loads(path.read_text(encoding='utf-8'))
        episode['cuts'][0].update(panel_count=4, render_size=[1024, 2048])
        save(path, episode)
        prompt = next_action(self.job, 'cut_a')['imagegen']['prompt']
        self.assertIn('exactly 4 sequential panels', prompt)
        self.assertIn('1024 x 2048', prompt)
        self.assertNotIn('or page collage', prompt)
        episode['cuts'][0].update(panel_count=1, render_size=[1536, 768])
        save(path, episode)
        self.assertIn('landscape', next_action(self.job, 'cut_a')['imagegen']['prompt'])
        episode['cuts'][0]['panel_count'] = 0
        save(path, episode)
        with self.assertRaisesRegex(ValueError, 'panel_count'):
            next_action(self.job, 'cut_a')

    def test_prepared_strip_brief_does_not_contradict_multi_panel_handoff(self):
        episode = json.loads(self.source.read_text(encoding='utf-8'))
        episode['cuts'][0].update(panel_count=4, render_size=[1024, 2048])
        save(self.source, episode)
        other_job = self.root / 'strip_job'
        prepare_job(self.source, other_job, self.root / 'characters.json')
        prompt = next_action(other_job, 'cut_a')['imagegen']['prompt']
        self.assertIn('exactly 4 sequential panels', prompt)
        self.assertIn('Intentional 4-panel webtoon strip render unit', prompt)
        self.assertNotIn('Single webtoon panel:', prompt)

    def test_legacy_and_tampered_generation_inputs_are_rejected_without_payload(self):
        path = self.job / "job.json"
        original = path.read_bytes()
        mutations = [
            lambda job: job.pop("generation_input_mode"),
            lambda job: job.update(generation_input_mode="image_reference"),
            lambda job: job.pop("generation_policy_version"),
            lambda job: job.update(generation_policy_version="unknown-policy"),
            lambda job: job["characters"]["min"].update(reference_images=[{
                "path": str(self.art), "sha256": digest(self.art)}]),
            lambda job: job["cuts"][0].update(reference_images=[{
                "path": str(self.art), "sha256": digest(self.art), "role": "character"}]),
            lambda job: job["cuts"][0].update(visual_reference_ids=["ref_0001"]),
        ]
        for index, mutate in enumerate(mutations):
            job = json.loads(original)
            mutate(job)
            save(path, job)
            with self.subTest(mutation=index):
                for cut_id in (None, "cut_a"):
                    with self.assertRaises(ValueError):
                        next_action(self.job, cut_id)
            self.assertEqual(path.read_bytes(), json.dumps(job, ensure_ascii=False).encode("utf-8"))
        path.write_bytes(original)

    def test_episode_image_injection_or_changed_cut_identity_blocks_generation(self):
        path = self.job / "conti/episode.json"
        original = path.read_bytes()
        mutations = [
            lambda episode: episode["cuts"][0].update(image=str(self.art)),
            lambda episode: episode["cuts"][0].update(atari=str(self.art)),
            lambda episode: episode["cuts"][0].update(background=str(self.art)),
            lambda episode: episode["cuts"][0].update(controls=[{"image": str(self.art)}]),
            lambda episode: episode["cuts"][0].update(id="different_cut"),
        ]
        for index, mutate in enumerate(mutations):
            episode = json.loads(original)
            mutate(episode)
            save(path, episode)
            with self.subTest(mutation=index), self.assertRaises(ValueError):
                next_action(self.job, "cut_a")
        path.write_bytes(original)

    def test_missing_actual_prompt_or_reference_declaration_prevents_ready_and_build_handoff(self):
        import_cut(self.job, "cut_a", self.art)
        import_cut(self.job, "cut_b", self.art)
        action = next_action(self.job)
        self.assertEqual(action["action"], "record_provenance")
        self.assertTrue(any("actual generation prompt" in issue for issue in action["issues"]))
        self.assertTrue(any("actual visual-reference" in issue for issue in action["issues"]))
        self.import_current("cut_a", replace=True)
        self.import_current("cut_b", replace=True)
        self.assertEqual(next_action(self.job)["action"], "build")
        job_path = self.job / "job.json"
        job = json.loads(job_path.read_text(encoding="utf-8"))
        job["cuts"][0]["imported"]["prompt"] += " changed without corresponding hash"
        save(job_path, job)
        action = next_action(self.job)
        self.assertEqual(action["action"], "record_provenance")
        self.assertTrue(any("prompt hash differs" in issue for issue in action["issues"]))

    def test_real_file_lifecycle_build_review_submission_ready_keeps_editorial_approval_pending(self):
        self.import_all()
        self.assertEqual(next_action(self.job)["action"], "build")
        manifest = build_job(self.job)
        self.assertTrue(job_status(self.job)["output_valid"])
        with Image.open(manifest.parent / "full_strip.png") as image:
            self.assertEqual(image.size, (800, 2720))
        action = next_action(self.job)
        self.assertEqual(action["action"], "review")
        self.assertEqual(len(action["raw_images"]), 2)
        self.assertEqual(action["output_manifest"], str(manifest))
        path, _ = self.report()
        self.assertEqual(submit_review(self.job, path)["counts"]["pass"], 14)
        action = next_action(self.job)
        self.assertEqual(action["action"], "plagiarism_check")
        self.assertEqual(action["plagiarism_review"]["status"], "not_checked")
        # This fixture checks routing only; it does not simulate a Jev judgment.
        with patch("src.operations.plagiarism_status", return_value={"status": "passed"}):
            action = next_action(self.job)
        self.assertEqual(action["action"], "ready")
        self.assertTrue(action["technical_output_valid"])
        self.assertEqual(action["agent_visual_review"], "passed")
        self.assertEqual(action["plagiarism_review"], "passed")
        self.assertEqual(action["editorial_approval"], "not_reviewed")

    def test_plagiarism_routing_blocks_each_incomplete_state_after_visual_review(self):
        self.import_all()
        build_job(self.job)
        path, _ = self.report()
        submit_review(self.job, path)
        original_job = (self.job / "job.json").read_bytes()
        original_review = (self.job / "review.json").read_bytes()
        for screening_status, expected_action, command in (
                ("not_checked", "plagiarism_check", "plagiarism"),
                ("stale", "plagiarism_check", "plagiarism"),
                ("error", "plagiarism_check", "plagiarism"),
                ("screened", "plagiarism_review", "plagiarism-review"),
                ("needs_human_review", "plagiarism_review", "plagiarism-review")):
            with self.subTest(status=screening_status):
                summary = {"status": screening_status, "issues": ["Routing fixture, not a Jev result"]}
                with patch("src.operations.plagiarism_status", return_value=summary) as check:
                    action = next_action(self.job)
                self.assertEqual(action["action"], expected_action)
                self.assertEqual(action["plagiarism_review"], summary)
                self.assertIn(f"factory.ps1 {command} ", action["command"])
                self.assertIn("--report FILE" if command == "plagiarism-review" else "--corpus FILE", action["command"])
                check.assert_called_once()
                self.assertEqual((self.job / "job.json").read_bytes(), original_job)
                self.assertEqual((self.job / "review.json").read_bytes(), original_review)

    def test_plagiarism_result_cannot_bypass_unsubmitted_visual_review(self):
        self.import_all()
        build_job(self.job)
        with patch("src.operations.plagiarism_status", return_value={"status": "passed"}) as check:
            self.assertEqual(next_action(self.job)["action"], "review")
        check.assert_not_called()

    def test_recorded_needs_fix_returns_specific_fix_handoff(self):
        self.import_all()
        build_job(self.job)
        path, review = self.report()
        review["cuts"]["cut_a"]["checks"]["lettering"].update(result="needs_fix", note="Fixture: balloon covers face")
        save(path, review)
        self.assertEqual(submit_review(self.job, path)["status"], "needs_fix")
        self.assertEqual(next_action(self.job)["action"], "fix_review")
        self.assertTrue(next_action(self.job, "cut_a")["replace"])

    def test_stale_review_report_cannot_replace_existing_record(self):
        self.import_all()
        build_job(self.job)
        path, review = self.report()
        submit_review(self.job, path)
        existing = (self.job / "review.json").read_bytes()
        for field in ("episode_sha256", "output_manifest_sha256", "image_sha256"):
            with self.subTest(field=field):
                changed = json.loads(json.dumps(review))
                target = changed["cuts"]["cut_a"] if field == "image_sha256" else changed
                target[field] = "0" * 64
                save(path, changed)
                with self.assertRaisesRegex(ValueError, "stale"):
                    submit_review(self.job, path)
                self.assertEqual((self.job / "review.json").read_bytes(), existing)

    def test_all_not_applicable_cut_never_passes_even_when_other_cut_has_passes(self):
        self.import_all()
        build_job(self.job)
        path, review = self.report()
        for check in review["cuts"]["cut_b"]["checks"].values():
            check.update(result="not_applicable", note="Fixture: no observation made")
        save(path, review)
        summary = submit_review(self.job, path)
        self.assertEqual(summary["status"], "not_reviewed")
        self.assertEqual(summary["counts"]["pass"], 7)
        self.assertTrue(any("cut_b" in issue for issue in summary["issues"]))
        self.assertEqual(next_action(self.job)["action"], "review")

    def test_replacement_preserves_custom_output_directory_and_returns_rebuild(self):
        self.import_all()
        destination = self.root / "final-webtoon"
        build_job(self.job, destination)
        self.import_current("cut_a", replace=True)
        action = next_action(self.job)
        self.assertEqual(action["action"], "build")
        self.assertEqual(action["output_dir"], str(destination.resolve()))
        self.assertTrue(action["overwrite"])
        manifest = build_job(self.job, overwrite=True)
        self.assertEqual(manifest.parent, destination.resolve())
        self.assertTrue(job_status(self.job)["output_valid"])


if __name__ == "__main__":
    unittest.main()
