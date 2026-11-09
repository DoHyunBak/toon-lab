"""Runner contract tests against the real HTTP client and a fake server."""

import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from PIL import Image

from src.comfy_client import ComfyClient, ComfyError
from src.comfy_runner import (DEFAULT_SERVER, load_workflow, main, run_workflow,
                              validate_completed_output)


GRAPH = {
    "render": {"class_type": "NativeCustomRender", "inputs": {"text": "An empty courtyard", "steps": 2},
               "_meta": {"title": "Authored native graph"}},
    "save": {"class_type": "SaveImage", "inputs": {"images": ["render", 0], "filename_prefix": "candidate"}},
}
OBJECT_INFO = {
    "NativeCustomRender": {"input": {"required": {"text": ["STRING"], "steps": ["INT", {"min": 1, "max": 8}]}}},
    "SaveImage": {"input": {"required": {"images": ["IMAGE"], "filename_prefix": ["STRING"]}}},
}


class Response(io.BytesIO):
    pass


class FakeServer:
    def __init__(self):
        self.calls = []
        self.queued = []
        self.info = copy.deepcopy(OBJECT_INFO)
        self.pending = False
        self.offline = False
        self.lose_submission_response = False
        self.image_count = 1
        self.completed = True
        self.now = 0
        buffer = io.BytesIO()
        Image.new("RGB", (12, 16), "white").save(buffer, "PNG")
        self.png = buffer.getvalue()

    def sleep(self, seconds):
        self.now += seconds

    def client(self):
        return ComfyClient(DEFAULT_SERVER, timeout=2, poll_interval=1, opener=self.open,
                           clock=lambda: self.now, sleeper=self.sleep)

    def open(self, request, timeout=None):
        method, path = request.get_method(), request.full_url.removeprefix(DEFAULT_SERVER)
        self.calls.append((method, path))
        if self.offline:
            raise urllib.error.URLError("offline test server")
        if path == "/prompt":
            self.queued.append(json.loads(request.data)["prompt"])
            if self.lose_submission_response:
                raise urllib.error.URLError("response lost after accepting prompt")
            result = {"prompt_id": "prompt-1"}
        elif path == "/system_stats":
            result = {"system": {"os": "test"}}
        elif path == "/object_info":
            result = self.info
        elif path == "/history/prompt-1":
            result = {} if self.pending else {
                "prompt-1": {"status": {"completed": self.completed}, "outputs": {"save": {
                    "images": [{"filename": f"result-{i}.png", "type": "output", "subfolder": ""}
                               for i in range(self.image_count)]}}}}
        elif path.startswith("/view?"):
            return Response(self.png)
        else:
            raise AssertionError(f"unexpected request: {method} {path}")
        return Response(json.dumps(result).encode())


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workflow = self.root / "authored.json"
        # Unusual spacing/newlines must survive the snapshot byte-for-byte.
        self.raw = (json.dumps(GRAPH, ensure_ascii=False, indent=3) + "\n\n").encode()
        self.workflow.write_bytes(self.raw)
        self.output = self.root / "output"
        self.server = FakeServer()

    def run_mode(self, mode):
        return run_workflow(self.workflow, self.output, mode=mode, client=self.server.client())

    def receipt(self):
        return json.loads((self.output / "receipt.json").read_text(encoding="utf-8"))

    def test_check_only_gets_system_and_installed_nodes_without_writing(self):
        result = self.run_mode("check")
        self.assertEqual(result["status"], "checked_not_queued")
        self.assertEqual(self.server.calls, [("GET", "/system_stats"), ("GET", "/object_info")])
        self.assertFalse(self.output.exists())
        self.assertEqual(result["rights_review"], "not_issued")
        self.assertEqual(result["quality_review"], "not_reviewed")

    def test_offline_check_has_no_post_or_output(self):
        self.server.offline = True
        with self.assertRaises(ComfyError):
            self.run_mode("check")
        self.assertFalse(self.output.exists())
        self.assertFalse(self.server.queued)

    def test_arbitrary_installed_graph_submitted_unchanged_once_and_receipt_binds_bytes(self):
        result = self.run_mode("execute")
        self.assertEqual(self.server.queued, [GRAPH])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["prompt_id"], "prompt-1")
        self.assertEqual(result["output_node_id"], "save")
        self.assertEqual((self.output / "workflow_api.json").read_bytes(), self.raw)
        receipt, workflow = validate_completed_output(self.output / "receipt.json", self.output / "image.png")
        self.assertEqual(receipt, result)
        self.assertEqual(workflow, self.output / "workflow_api.json")
        self.assertEqual(result["output"]["width"], 12)
        self.assertEqual(result["output"]["height"], 16)
        self.assertEqual([m for m, _ in self.server.calls].count("POST"), 1)
        self.assertFalse(any("upload" in p for _, p in self.server.calls))

    def test_timeout_persists_prompt_id_and_resume_never_posts(self):
        self.server.pending = True
        with self.assertRaises(TimeoutError):
            self.run_mode("execute")
        receipt = self.receipt()
        self.assertEqual(receipt["status"], "submitted")
        self.assertEqual(receipt["prompt_id"], "prompt-1")
        self.assertFalse((self.output / "image.png").exists())
        self.server.pending = False
        self.server.calls.clear()
        self.assertEqual(self.run_mode("resume")["status"], "completed")
        self.assertEqual(len(self.server.queued), 1)
        self.assertTrue(all(method == "GET" for method, _ in self.server.calls))
        self.assertTrue(all(path.startswith(("/history/", "/view?")) for _, path in self.server.calls))

    def test_completed_resume_is_local_integrity_check(self):
        result = self.run_mode("execute")
        self.server.calls.clear()
        self.assertEqual(self.run_mode("resume"), result)
        self.assertEqual(self.server.calls, [])

    def test_unknown_queue_outcome_is_recorded_and_not_resubmitted(self):
        self.server.lose_submission_response = True
        with self.assertRaises(ComfyError):
            self.run_mode("execute")
        self.assertEqual(self.receipt()["status"], "submission_unknown")
        self.assertIsNone(self.receipt()["prompt_id"])
        self.server.calls.clear()
        with self.assertRaisesRegex(ValueError, "do not automatically requeue"):
            self.run_mode("resume")
        self.assertEqual(len(self.server.queued), 1)
        self.assertEqual(self.server.calls, [])

    def test_existing_output_directory_is_preserved_and_never_queued(self):
        self.output.mkdir()
        prior = self.output / "important.txt"
        prior.write_text("preserve")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.run_mode("execute")
        self.assertEqual(prior.read_text(), "preserve")
        self.assertEqual(self.server.calls, [])

    def test_resume_refuses_modified_workflow_server_or_snapshot_without_network(self):
        self.server.pending = True
        with self.assertRaises(TimeoutError):
            self.run_mode("execute")
        self.server.calls.clear()
        self.workflow.write_bytes(self.raw + b" ")
        with self.assertRaisesRegex(ValueError, "not bound"):
            self.run_mode("resume")
        self.workflow.write_bytes(self.raw)
        with self.assertRaisesRegex(ValueError, "not bound"):
            run_workflow(self.workflow, self.output, mode="resume", server="http://localhost:8188")
        (self.output / "workflow_api.json").write_bytes(self.raw + b" ")
        with self.assertRaisesRegex(ValueError, "snapshot differs"):
            self.run_mode("resume")
        self.assertEqual(self.server.calls, [])

    def test_completed_output_hash_change_is_rejected(self):
        self.run_mode("execute")
        Image.new("RGB", (12, 16), "black").save(self.output / "image.png", "PNG")
        with self.assertRaisesRegex(ValueError, "image bytes/dimensions differ"):
            validate_completed_output(self.output / "receipt.json", self.output / "image.png")

    def test_multiple_output_images_are_not_silently_truncated(self):
        self.server.image_count = 2
        with self.assertRaisesRegex(ComfyError, "exactly one image"):
            self.run_mode("execute")
        self.assertFalse((self.output / "image.png").exists())
        self.assertFalse(any(path.startswith("/view?") for _, path in self.server.calls))
        self.assertEqual(self.receipt()["prompt_id"], "prompt-1")

    def test_output_without_completion_confirmation_remains_submitted(self):
        self.server.completed = False
        with self.assertRaisesRegex(ComfyError, "not confirmed completed"):
            self.run_mode("execute")
        self.assertEqual(self.receipt()["status"], "submitted")
        self.assertFalse((self.output / "image.png").exists())

    def test_missing_nodes_and_unavailable_values_fail_before_queue(self):
        del self.server.info["NativeCustomRender"]
        with self.assertRaisesRegex(ComfyError, "missing core node"):
            self.run_mode("execute")
        self.assertFalse(self.output.exists())
        self.assertFalse(self.server.queued)

    def test_malformed_native_and_ui_graphs_rejected_before_network(self):
        invalid = [{"nodes": [], "links": []}, [], {},
                   {"save": {"type": "SaveImage", "inputs": {}}}]
        for graph in invalid:
            with self.subTest(graph=graph):
                self.workflow.write_text(json.dumps(graph))
                with self.assertRaises(ValueError):
                    self.run_mode("check")
        self.assertEqual(self.server.calls, [])

    def test_invalid_links_and_multiple_save_nodes_are_rejected(self):
        for link in (["absent", 0], ["render", -1], ["render", True], ["render"], ["render", 0, 1]):
            graph = copy.deepcopy(GRAPH)
            graph["save"]["inputs"]["images"] = link
            self.workflow.write_text(json.dumps(graph))
            with self.subTest(link=link), self.assertRaisesRegex(ValueError, "invalid.*link"):
                load_workflow(self.workflow)
        graph = copy.deepcopy(GRAPH)
        graph["save2"] = graph["save"]
        self.workflow.write_text(json.dumps(graph))
        with self.assertRaisesRegex(ValueError, "exactly one SaveImage"):
            load_workflow(self.workflow)

    def test_duplicate_keys_and_nonfinite_numbers_rejected(self):
        for raw in (b'{"x":{},"x":{}}', b'{"x":NaN}', b'{"x":1e999}'):
            self.workflow.write_bytes(raw)
            with self.assertRaises(ValueError):
                load_workflow(self.workflow)

    def test_validator_uses_the_supplied_receipt_instead_of_a_neighbor(self):
        self.run_mode("execute")
        renamed = self.output / "import-receipt.json"
        modified = self.receipt()
        modified["status"] = "submitted"
        renamed.write_text(json.dumps(modified))
        with self.assertRaisesRegex(ValueError, "completed ComfyUI image"):
            validate_completed_output(renamed, self.output / "image.png")

    def test_remote_server_requires_explicit_optin_before_network(self):
        with self.assertRaisesRegex(ValueError, "allow-remote"):
            run_workflow(self.workflow, self.output, server="https://render.example.invalid")
        self.assertFalse(self.output.exists())

    def test_cli_error_returns_nonzero(self):
        self.workflow.write_text('{"nodes":[]}')
        with patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(main([str(self.workflow), "--output-dir", str(self.output), "--check"]), 1)


if __name__ == "__main__":
    unittest.main()
