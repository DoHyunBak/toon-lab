"""Synthetic legal-QA control-flow fixtures; never legal or model-accuracy claims."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from src.factory import _load, build_job, import_cut, prepare_job
from src.legal_qa import (CRITERIA, DOMAINS, _today, legal_status,
                          run_legal_check, submit_legal_review)
from src.typesafe_jev import DEFAULT_MODEL


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LegalQATests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="legal-qa-test-", dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.job = self.root / "job"
        self.source = self.root / "episode.json"
        save(self.source, {"title": "Synthetic QA fixture", "cuts": [
            {"id": "cut_a", "description": "A test rectangle, not production art", "characters": [], "dialogue": []}]})
        prepare_job(self.source, self.job)
        self.evidence = self.root / "evidence.md"
        self.evidence.write_text("PRIVATE_RAW_EVIDENCE_SENTINEL. Synthetic fixture record only.", encoding="utf-8")
        law_text = "Synthetic rule: the operator must have the declared permission for the requested act."
        self.index = self.root / "index.json"
        self.data = {
            "schema_version": 1, "jurisdiction": "KR", "as_of": _today(),
            "scope": "Synthetic workflow control-flow fixture; not a legal finding",
            "external_processing_allowed": True, "rights_basis": "Locally authored synthetic test summaries",
            "sources": [{"id": "synthetic_rule", "law_name": "Synthetic fixture, not real law",
                         "article": "Test article", "version": "test-version", "effective_on": "2020-01-01",
                         "checked_on": _today(), "official_url": "https://www.law.go.kr/법령/저작권법/제7조",
                         "text": law_text, "text_sha256": hashlib.sha256(law_text.encode()).hexdigest()}],
            "actions": [],
            "coverage": {key: {"status": "not_applicable", "reason": "Synthetic test scope only", "action_ids": []}
                         for key in DOMAINS},
        }
        for identifier in ("owned_use", "external_summary"):
            self.data["actions"].append({"id": identifier, "stages": ["preflight", "final"],
                "description": "Use a locally authored test fixture", "facts": "The test operator authored and authorized the fixture.",
                "law_ids": ["synthetic_rule"], "evidence": [{"id": "fixture_record", "path": "evidence.md",
                    "sha256": digest(self.evidence), "summary": "A synthetic authorship record exists locally.",
                    "external_processing_allowed": True, "rights_basis": "Operator authored the synthetic summary"}]})
        self.data["coverage"]["copyright"] = {"status": "applicable", "reason": "Synthetic fixture exercise",
                                               "action_ids": ["owned_use"]}
        self.data["coverage"]["external_processing"] = {"status": "applicable", "reason": "Synthetic external summary exercise",
                                                        "action_ids": ["external_summary"]}
        save(self.index, self.data)

    def status(self, stage="preflight"):
        root, job = _load(self.job)
        return legal_status(root, job, stage)

    def response(self, choice="supported", *, tied=False, zero=False):
        def respond(state, questions, *, model=DEFAULT_MODEL):
            probabilities = {key: (1 / len(CRITERIA) if tied else float(key == choice)) for key in CRITERIA}
            return {"model": model, "answers": {"assessment": {
                "type": "choice", "choice": choice, "confidence": 0.0 if zero else 1.0,
                "probabilities": probabilities}}, "usage": {"input_tokens": 1, "output_tokens": 0}}
        return respond

    def screen(self, stage="preflight", **kwargs):
        with patch("src.legal_qa.ask", side_effect=self.response()) as api:
            result = run_legal_check(self.job, self.index, stage=stage, **kwargs)
        return result, api

    def review(self, stage="preflight", decision="accept"):
        check = self.job / f"legal_{stage}.check.json"
        report = {"check_sha256": digest(check), "reviewer": "Synthetic test observer",
                  "decision": decision, "notes": "Test control flow only, not a legal or human-identity attestation",
                  "action_reviews": {key: {"decision": decision, "note": "Fixture evidence was examined for the test"}
                                     for key in read(check)["actions"]}}
        path = self.root / f"{stage}-review.json"
        save(path, report)
        return path, report

    def passed_preflight(self):
        self.screen()
        path, _ = self.review()
        return submit_legal_review(self.job, path)

    def build(self):
        art = self.root / "art.png"
        Image.new("RGB", (320, 480), "#557788").save(art)
        prompt = self.root / "prompt.txt"
        prompt.write_text("Synthetic test input", encoding="utf-8")
        import_cut(self.job, "cut_a", art, prompt, used_reference_ids=[])
        return build_job(self.job)

    def test_no_record_is_read_only_and_never_calls_api(self):
        before = (self.job / "job.json").read_bytes()
        with patch("src.legal_qa.ask") as api:
            self.assertEqual(self.status()["status"], "not_checked")
            self.assertEqual(self.status("final")["status"], "not_checked")
        api.assert_not_called()
        self.assertEqual(before, (self.job / "job.json").read_bytes())
        self.assertFalse((self.job / "legal_preflight.check.json").exists())

    def test_current_check_is_scoped_and_requires_separate_observation(self):
        result, api = self.screen()
        self.assertEqual(result["status"], "screened")
        self.assertEqual(api.call_count, 2)
        self.assertEqual(result["legal_clearance"], "not_issued")
        state = api.call_args.args[0]
        self.assertNotIn("path", state["action"]["evidence"][0])
        self.assertNotIn("PRIVATE_RAW_EVIDENCE_SENTINEL", json.dumps(state))
        contents = (self.job / "legal_preflight.check.json").read_text(encoding="utf-8")
        self.assertNotIn(self.data["actions"][0]["facts"], contents)
        self.assertNotIn("PRIVATE_RAW_EVIDENCE_SENTINEL", contents)
        path, _ = self.review()
        self.assertEqual(submit_legal_review(self.job, path)["status"], "passed")
        with patch("src.legal_qa.ask") as api:
            self.assertEqual(self.status()["status"], "passed")
        api.assert_not_called()

    def test_invalid_index_errors_never_echo_supplied_values(self):
        marker = "PRIVATE_FACT_MARKER_FOR_INVALID_INPUT"
        for target, field, value in (
                ("source", "effective_on", marker),
                ("source", "checked_on", marker),
                ("source", "official_url", f"https://www.law.go.kr:{marker}/법령/저작권법"),
                ("evidence", "path", f"../{marker}.md")):
            data = json.loads(json.dumps(self.data))
            item = data["sources"][0] if target == "source" else data["actions"][0]["evidence"][0]
            item[field] = value
            save(self.index, data)
            with self.subTest(field=field), patch("src.legal_qa.ask") as api:
                with self.assertRaises(ValueError) as error:
                    run_legal_check(self.job, self.index)
            self.assertNotIn(marker, str(error.exception))
            self.assertIsNone(error.exception.__cause__)
            self.assertTrue(error.exception.__suppress_context__)
            api.assert_not_called()

    def test_permission_missing_scope_and_bad_sources_fail_before_network(self):
        mutations = [lambda d: d.update(external_processing_allowed=False),
                     lambda d: d.update(rights_basis=""), lambda d: d.update(actions=[]),
                     lambda d: d["sources"][0].update(text_sha256="0" * 64),
                     lambda d: d["sources"][0].update(checked_on="2020-01-01"),
                     lambda d: d["sources"][0].update(effective_on="2999-01-01"),
                     lambda d: d["sources"][0].update(official_url="https://example.com/law"),
                     lambda d: d["sources"][0].update(official_url="https://law.go.kr/?OC=hidden"),
                     lambda d: d["actions"][0].update(law_ids=["missing_rule"]),
                     lambda d: d["actions"][0].update(evidence=[]),
                     lambda d: d["coverage"].pop("privacy"),
                     lambda d: d["coverage"]["copyright"].update(action_ids=[]),
                     lambda d: d["actions"][0]["evidence"][0].update(external_processing_allowed=False),
                     lambda d: d["actions"][0]["evidence"][0].update(path="../outside.txt"),
                     lambda d: d["actions"][0].update(facts="LAW_OC=never-transmit-this-value"),
                     lambda d: d["actions"][0].update(law_ids=[{}])]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                data = json.loads(json.dumps(self.data))
                mutate(data)
                save(self.index, data)
                with patch("src.legal_qa.ask") as api:
                    with self.assertRaises(ValueError):
                        run_legal_check(self.job, self.index)
                api.assert_not_called()

    def test_risk_insufficient_and_uncertainty_cannot_be_manually_overridden(self):
        for kwargs in ({"choice": "risk"}, {"choice": "insufficient"}, {"tied": True}, {"zero": True}):
            with self.subTest(kwargs=kwargs):
                check = self.job / "legal_preflight.check.json"
                check.unlink(missing_ok=True)
                with patch("src.legal_qa.ask", side_effect=self.response(**kwargs)):
                    result = run_legal_check(self.job, self.index)
                self.assertEqual(result["status"], "blocked")
                path, _ = self.review()
                with self.assertRaises(ValueError):
                    submit_legal_review(self.job, path)
                self.assertEqual(self.status()["status"], "blocked")

    def test_partial_budget_resume_and_service_failure_never_issue_pass(self):
        result, api = self.screen(max_requests=1)
        self.assertEqual(result["status"], "error")
        self.assertEqual(api.call_count, 1)
        with patch("src.legal_qa.ask", side_effect=ValueError("Potentially sensitive service response")):
            result = run_legal_check(self.job, self.index)
        self.assertEqual(result["status"], "error")
        self.assertNotIn("Potentially sensitive", (self.job / "legal_preflight.check.json").read_text())
        result, api = self.screen(max_requests=1)
        self.assertEqual(api.call_count, 1)
        self.assertEqual(result["status"], "screened")
        result, api = self.screen()
        self.assertEqual(api.call_count, 0)
        self.assertEqual(result["status"], "screened")

    def test_changed_plan_evidence_or_date_invalidates_results(self):
        self.passed_preflight()
        prompt = self.job / "prompts/cut_a.txt"
        original = prompt.read_bytes()
        prompt.write_bytes(original + b"changed")
        self.assertEqual(self.status()["status"], "stale")
        prompt.write_bytes(original)
        self.evidence.write_text("changed local evidence", encoding="utf-8")
        self.assertEqual(self.status()["status"], "stale")
        with patch("src.legal_qa._today", return_value="2999-01-01"):
            self.assertEqual(self.status()["status"], "stale")

    def test_generation_mode_or_policy_change_invalidates_preflight(self):
        self.passed_preflight()
        path = self.job / "job.json"
        original = path.read_bytes()
        for field, value in (("generation_input_mode", "image_reference"),
                             ("generation_policy_version", "changed-policy")):
            job = json.loads(original)
            job[field] = value
            save(path, job)
            with self.subTest(field=field):
                self.assertEqual(self.status()["status"], "stale")
                with patch("src.legal_qa.ask") as api:
                    with self.assertRaises(ValueError):
                        run_legal_check(self.job, self.index)
                api.assert_not_called()
        path.write_bytes(original)

    def test_generation_image_injection_cannot_reuse_passed_preflight(self):
        self.passed_preflight()
        job_path = self.job / "job.json"
        job = read(job_path)
        job["cuts"][0]["reference_images"] = [{
            "path": "never-read-reference.png", "sha256": "0" * 64, "role": "character"}]
        save(job_path, job)
        self.assertEqual(self.status()["status"], "stale")
        with patch("src.legal_qa.ask") as api:
            with self.assertRaises(ValueError):
                run_legal_check(self.job, self.index)
        api.assert_not_called()

    def test_stage_scope_cannot_omit_applicable_domain_or_add_unscoped_actions(self):
        data = json.loads(json.dumps(self.data))
        data["actions"][1]["stages"] = ["preflight"]
        save(self.index, data)
        self.passed_preflight()
        self.build()
        with patch("src.legal_qa.ask") as api:
            with self.assertRaises(ValueError):
                run_legal_check(self.job, self.index, stage="final")
        api.assert_not_called()
        data = json.loads(json.dumps(self.data))
        data["coverage"]["external_processing"] = {"status": "not_applicable", "reason": "Fixture only", "action_ids": []}
        save(self.index, data)
        with patch("src.legal_qa.ask") as api:
            with self.assertRaises(ValueError):
                run_legal_check(self.job, self.index)
        api.assert_not_called()

    def test_reference_plan_injection_is_rejected_before_network(self):
        self.passed_preflight()
        plan = self.job / "reference_plan.json"
        data = read(plan)
        data["cuts"][0]["references"] = [{
            "id": "ref_0001", "path": "never-read-reference.png",
            "metadata_path": "never-read-metadata.json", "sha256": "0" * 64,
            "metadata_sha256": "0" * 64}]
        save(plan, data)
        self.assertEqual(self.status()["status"], "stale")
        with patch("src.legal_qa.ask") as api:
            with self.assertRaises(ValueError):
                run_legal_check(self.job, self.index)
        api.assert_not_called()

    def test_preflight_survives_import_and_build_final_binds_actual_output(self):
        self.assertEqual(self.passed_preflight()["status"], "passed")
        output = self.build()
        self.assertEqual(self.status()["status"], "passed")
        result, api = self.screen("final")
        self.assertEqual(result["status"], "screened")
        self.assertEqual(api.call_count, 2)
        path, _ = self.review("final")
        self.assertEqual(submit_legal_review(self.job, path, stage="final")["status"], "passed")
        manifest = read(output)
        art = output.parent / manifest["full"]["path"]
        art.write_bytes(art.read_bytes() + b"changed")
        self.assertEqual(self.status("final")["status"], "stale")

    def test_final_needs_current_preflight_and_output_before_network(self):
        with patch("src.legal_qa.ask") as api:
            with self.assertRaises(ValueError):
                run_legal_check(self.job, self.index, stage="final")
        api.assert_not_called()
        self.passed_preflight()
        with patch("src.legal_qa.ask") as api:
            with self.assertRaises(ValueError):
                run_legal_check(self.job, self.index, stage="final")
        api.assert_not_called()

    def test_review_coverage_and_hash_must_match_and_no_rejection_passes(self):
        self.screen()
        path, report = self.review()
        report["action_reviews"].pop("owned_use")
        save(path, report)
        with self.assertRaises(ValueError):
            submit_legal_review(self.job, path)
        path, report = self.review()
        report["check_sha256"] = "0" * 64
        save(path, report)
        with self.assertRaises(ValueError):
            submit_legal_review(self.job, path)
        path, _ = self.review(decision="needs_fix")
        self.assertNotEqual(submit_legal_review(self.job, path)["status"], "passed")

    def test_model_mismatch_malformed_and_inflight_changes_remain_blocked(self):
        for mode in ("model", "coverage", "inflight"):
            with self.subTest(mode=mode):
                (self.job / "legal_preflight.check.json").unlink(missing_ok=True)
                def invalid(state, questions, *, model=DEFAULT_MODEL):
                    response = self.response()(state, questions, model=model)
                    if mode == "model":
                        response["model"] = "jev-0.0.0"
                    elif mode == "coverage":
                        response["answers"]["unexpected"] = response["answers"]["assessment"]
                    else:
                        prompt = self.job / "prompts/cut_a.txt"
                        prompt.write_text(prompt.read_text() + "change", encoding="utf-8")
                    return response
                with patch("src.legal_qa.ask", side_effect=invalid):
                    result = run_legal_check(self.job, self.index)
                self.assertNotEqual(result["status"], "passed")


if __name__ == "__main__":
    unittest.main()
