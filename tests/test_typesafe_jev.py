"""TypeSafe contract regressions; all service traffic is mocked."""
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from PIL import Image, PngImagePlugin

from src import typesafe_jev as jev


class _Response:
    status = 200

    def __init__(self, data):
        self.body = data if isinstance(data, bytes) else json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.body[:limit]


class TypeSafeJevTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="jev-contract-test-", dir=Path(__file__).resolve().parents[1])
        self.addCleanup(temporary.cleanup)
        self.local_env = Path(temporary.name) / ".env"
        local_file = patch.object(jev, "LOCAL_ENV_FILE", self.local_env)
        local_file.start()
        self.addCleanup(local_file.stop)
        environment = patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-" + "only-key", "TYPESAFE_API_TOKEN": ""})
        environment.start()
        self.addCleanup(environment.stop)
        opener = patch.object(jev.request, "build_opener")
        self.builder = opener.start()
        self.addCleanup(opener.stop)
        self.http = self.builder.return_value.open
        self.options = {"similar": "Distinctive resemblance", "different": "No distinctive resemblance"}
        self.questions = {"relation": {"type": "choice", "instructions": "Compare supplied evidence.",
                                       "criteria": self.options}}
        self.answer = {"type": "choice", "choice": "similar", "confidence": 0.8,
                       "probabilities": {"similar": 0.9, "different": 0.1}}
        self.response = {"model": jev.DEFAULT_MODEL, "answers": {"relation": self.answer},
                         "usage": {"input_tokens": 15, "output_tokens": 5}}
        self.http.return_value = _Response(self.response)

    @staticmethod
    def decoded(asset):
        return Image.open(io.BytesIO(base64.b64decode(asset["data_base64"])))

    def test_post_contract_headers_utf8_and_pinned_model(self):
        asset = jev.image_asset(Image.new("RGB", (300, 300)))
        result = jev.ask({"target": "image-uuid", "label": "검토"}, self.questions, {"image-uuid": asset})
        sent = self.http.call_args.args[0]
        body = json.loads(sent.data)
        self.assertEqual(sent.full_url, "https://api.typesafe.ai/v1/systemone")
        self.assertEqual(sent.method, "POST")
        self.assertEqual(sent.get_header("Authorization"), "Bearer test-only-key")
        self.assertEqual(sent.get_header("Typesafe-danger-zone-images"), "true")
        self.assertEqual(body["state"]["label"], "검토")
        self.assertEqual(body["model"], "jev-1.13.0")
        self.assertEqual(body["assets"]["image-uuid"], asset)
        self.assertEqual(self.http.call_args.kwargs["timeout"], 90)
        self.assertEqual(result, self.response)

    def test_get_models_contract(self):
        models = {"models": [{"name": "jev-1.13.0", "description": "General purpose", "release_date": "2026-09-15"}]}
        self.http.return_value = _Response(models)
        self.assertEqual(jev.list_models(), models)
        sent = self.http.call_args.args[0]
        self.assertEqual(sent.full_url, "https://api.typesafe.ai/v1/models")
        self.assertEqual(sent.method, "GET")
        self.assertIsNone(sent.data)
        self.http.return_value = _Response({"models": [{"name": "jev-1.13.0"}]})
        with self.assertRaisesRegex(ValueError, "model list"):
            jev.list_models()

    def test_credentials_are_validated_without_network_and_alias_is_supported(self):
        for key in ("", "internal whitespace", "한글"):
            with self.subTest(key=key), patch.dict(os.environ, {"TYPESAFE_API_KEY": key}):
                with self.assertRaisesRegex(ValueError, "credential"):
                    jev.ask("data", self.questions)
        self.http.assert_not_called()
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": " ", "TYPESAFE_API_TOKEN": "test-only-token"}):
            jev.ask("data", self.questions)
        self.assertEqual(self.http.call_args.args[0].get_header("Authorization"), "Bearer test-only-token")

    def test_project_dotenv_nonempty_key_has_priority_with_bom_spaces_and_quotes(self):
        for text in ("TYPESAFE_API_KEY=local-test-key\n",
                     "\ufeffTYPESAFE_API_KEY=local-test-key\n",
                     "  TYPESAFE_API_KEY" + " = 'local-test-key'  \n",
                     'TYPESAFE_API_KEY' + ' = "local-test-key" # local only\n',
                     "TYPESAFE_API_KEY=local-test-key # local only\n"):
            self.local_env.write_text(text, encoding="utf-8")
            with self.subTest(format=text.split("=", 1)[0]):
                jev.ask("data", self.questions)
                self.assertEqual(self.http.call_args.args[0].get_header("Authorization"), "Bearer local-test-key")
                self.assertEqual(os.environ["TYPESAFE_API_KEY"], "test-only-key")

    def test_absent_or_empty_file_key_falls_back_without_exporting_other_values(self):
        for text in ("UNRELATED_TEST=changed\n", "TYPESAFE_API_KEY=\n", "TYPESAFE_API_KEY='  '\n"):
            self.local_env.write_text(text, encoding="utf-8")
            with self.subTest(text=text), patch.dict(os.environ, {"UNRELATED_TEST": "unchanged"}):
                jev.ask("data", self.questions)
                self.assertEqual(self.http.call_args.args[0].get_header("Authorization"), "Bearer test-only-key")
                self.assertEqual(os.environ["UNRELATED_TEST"], "unchanged")
        self.local_env.write_text("TYPESAFE_API_TOKEN=not-imported\n", encoding="utf-8")
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "", "TYPESAFE_API_TOKEN": "environment-token"}):
            jev.ask("data", self.questions)
            self.assertEqual(self.http.call_args.args[0].get_header("Authorization"), "Bearer environment-token")

    def test_duplicate_or_malformed_dotenv_is_rejected_before_service_call(self):
        for text in ("TYPESAFE_API_KEY=first-private-value\nTYPESAFE_API_KEY=second-private-value\n",
                     "TYPESAFE_API_KEY=\nTYPESAFE_API_KEY=second-private-value\n",
                     "TYPESAFE_API_KEY\n", "TYPESAFE_API_KEY missing-equals\n",
                     'TYPESAFE_API_KEY' + '="private-unclosed\n', 'TYPESAFE_API_KEY' + '="private-value" trailing-data\n'):
            self.local_env.write_text(text, encoding="utf-8")
            with self.subTest(kind="duplicate" if text.count("=") > 1 else "malformed"):
                with self.assertRaisesRegex(ValueError, "^TypeSafe local credential assignment is (invalid|duplicated)$"):
                    jev.ask("data", self.questions)
        self.http.assert_not_called()

    def test_dotenv_read_and_encoding_errors_are_sanitized(self):
        self.local_env.write_bytes(b"TYPESAFE_API_KEY=\xffprivate-value")
        with self.assertRaisesRegex(ValueError, "^TypeSafe local credential file cannot be read$"):
            jev.ask("data", self.questions)
        with patch.object(Path, "read_text", side_effect=PermissionError("private-path-or-key")):
            with self.assertRaisesRegex(ValueError, "^TypeSafe local credential file cannot be read$"):
                jev.ask("data", self.questions)
        self.http.assert_not_called()

    def test_redirects_are_not_followed_with_credentials(self):
        self.assertIsNone(jev._NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.test"))
        self.http.side_effect = HTTPError("https://api.typesafe.ai", 302, "private details", {}, io.BytesIO())
        with self.assertRaisesRegex(ValueError, "^TypeSafe service returned HTTP 302$"):
            jev.ask("data", self.questions)
        self.assertEqual(self.builder.call_args.args, (jev._NoRedirect,))
        self.assertEqual(self.http.call_count, 1)

    def test_http_failures_are_sanitized_and_not_retried(self):
        for status in (400, 401, 413, 429, 500, 503):
            self.http.reset_mock()
            self.http.side_effect = HTTPError("https://api.typesafe.ai", status, "private credential body", {},
                                              io.BytesIO(b"private manuscript body"))
            with self.subTest(status=status), self.assertRaises(ValueError) as caught:
                jev.ask("private manuscript", self.questions)
            self.assertEqual(str(caught.exception), f"TypeSafe service returned HTTP {status}")
            self.assertIsNone(caught.exception.__cause__)
            self.assertEqual(self.http.call_count, 1)

    def test_connection_failure_does_not_leak_original_error(self):
        self.http.side_effect = URLError("private URL, credential and body")
        with self.assertRaises(ValueError) as caught:
            jev.ask("data", self.questions)
        self.assertEqual(str(caught.exception), "TypeSafe service connection failed or timed out")
        self.assertEqual(self.http.call_count, 1)

    def test_invalid_json_nonfinite_json_and_nonobject_are_rejected(self):
        for body in (b"private invalid JSON", b'{"value":NaN}', b"[]"):
            self.http.return_value = _Response(body)
            with self.subTest(body=body), self.assertRaises(ValueError):
                jev.ask("data", self.questions)

    def test_changed_model_or_answer_coverage_never_passes(self):
        for mutate in (lambda r: r.update(model="jev-1.14.0"),
                       lambda r: r.update(answers={}),
                       lambda r: r["answers"].update(extra=self.answer)):
            response = copy.deepcopy(self.response)
            mutate(response)
            self.http.return_value = _Response(response)
            with self.subTest(response=response), self.assertRaisesRegex(ValueError, "do not match"):
                jev.ask("data", self.questions)

    def test_choice_types_ranges_distribution_coverage_and_argmax(self):
        self.assertEqual(jev.validate_choice(self.answer, self.options), self.answer)
        changes = ({"confidence": True}, {"confidence": -0.1}, {"confidence": float("nan")},
                   {"confidence": float("inf")}, {"choice": "unknown"}, {"type": "noul"},
                   {"probabilities": {"similar": 0.9}},
                   {"probabilities": {"similar": 0.9, "different": 0.1, "extra": 0}},
                   {"probabilities": {"similar": 0.4, "different": 0.1}},
                   {"probabilities": {"similar": 0.4, "different": 0.6}},
                   {"probabilities": {"similar": 10 ** 400, "different": 0.1}},
                   {"probabilities": {"similar": True, "different": 0}})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                jev.validate_choice({**self.answer, **change}, self.options)

    def test_small_rounding_tolerance_and_tied_maximum_are_supported(self):
        answer = {**self.answer, "probabilities": {"similar": 0.5, "different": 0.49}}
        self.assertEqual(jev.validate_choice(answer, self.options), answer)
        answer = {**self.answer, "probabilities": {"similar": 0.5, "different": 0.5}}
        self.assertEqual(jev.validate_choice(answer, self.options), answer)

    def test_noul_and_optional_usage_are_validated(self):
        questions = {"visible": {"type": "noul", "instructions": "Is the subject visible?"}}
        response = {"model": jev.DEFAULT_MODEL, "answers": {"visible": {"type": "noul", "noul": 0.1}}}
        self.http.return_value = _Response(response)
        self.assertEqual(jev.ask("data", questions), response)
        for value in (True, -0.1, 1.1, None):
            response["answers"]["visible"]["noul"] = value
            self.http.return_value = _Response(response)
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "Noul"):
                jev.ask("data", questions)
        for usage in ({"input_tokens": True}, {"output_tokens": -1}, {"input_tokens": 2.5}, None):
            self.http.return_value = _Response({**self.response, "usage": usage})
            with self.subTest(usage=usage), self.assertRaisesRegex(ValueError, "token usage"):
                jev.ask("data", self.questions)

    def test_invalid_requests_do_not_call_service(self):
        for questions in ({}, {"q": {"type": "box", "instructions": "Locate object"}},
                          {"q": {"type": "choice", "instructions": "Choose", "criteria": {"only": "one"}}}):
            with self.subTest(questions=questions), self.assertRaises(ValueError):
                jev.ask("data", questions)
        with self.assertRaisesRegex(ValueError, "pinned"):
            jev.ask("data", self.questions, model="jev-latest")
        with self.assertRaisesRegex(ValueError, "finite UTF-8 JSON"):
            jev.ask({"not_finite": float("nan")}, self.questions)
        for timeout in (0, -1, True, float("inf"), 10 ** 400):
            with self.subTest(timeout=timeout), self.assertRaisesRegex(ValueError, "timeout"):
                jev.ask("data", self.questions, timeout=timeout)
        self.http.assert_not_called()

    def test_request_and_response_body_budget(self):
        with patch.object(jev, "MAX_BODY_BYTES", 100):
            with self.assertRaisesRegex(ValueError, "request body exceeds"):
                jev.ask("x" * 101, self.questions)
            self.http.assert_not_called()
            self.http.return_value = _Response(b"x" * 101)
            with self.assertRaisesRegex(ValueError, "response exceeds"):
                jev.list_models()

    def test_asset_base64_and_decoded_size_budget(self):
        asset = {"type": "image", "format": "png", "data_base64": "data:image/png;base64,invalid"}
        with self.assertRaisesRegex(ValueError, "base64"):
            jev.ask("image-id", self.questions, {"image-id": asset})
        asset["data_base64"] = base64.b64encode(b"1234").decode()
        with patch.object(jev, "MAX_IMAGE_BYTES", 3), self.assertRaisesRegex(ValueError, "16 MiB"):
            jev.ask("image-id", self.questions, {"image-id": asset})
        self.http.assert_not_called()

    def test_normalization_preserves_aspect_and_pads_to_image_limits(self):
        for size, expected in (((20, 2000), (280, 1568)), ((2000, 400), (1568, 314)),
                               ((200, 100), (280, 280)), ((300, 400), (300, 400))):
            original = Image.new("RGBA", size, (10, 30, 50, 0))
            with self.subTest(size=size):
                asset = jev.image_asset(original)
                with self.decoded(asset) as image:
                    self.assertEqual(image.size, expected)
                    self.assertEqual(image.mode, "RGB")
                    self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))
                self.assertEqual(original.size, size)
                self.assertEqual(original.getpixel((0, 0)), (10, 30, 50, 0))

    def test_crop_and_source_file_remain_unchanged_and_metadata_is_removed(self):
        with tempfile.TemporaryDirectory(prefix="jev-image-test-", dir=Path(__file__).resolve().parents[1]) as directory:
            path = Path(directory) / "source.png"
            metadata = PngImagePlugin.PngInfo()
            metadata.add_text("private-note", "do not transmit source metadata")
            Image.new("RGB", (1000, 400), "red").save(path, pnginfo=metadata)
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            asset = jev.image_asset(path, (50, 20, 450, 300))
            with self.decoded(asset) as image:
                self.assertEqual(image.size, (400, 280))
                self.assertNotIn("private-note", image.info)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
        original = Image.new("RGB", (400, 300))
        for box in ((-1, 0, 200, 200), (0, 0, 500, 200), (0, 0, 0, 200), (0.5, 0, 200, 200)):
            with self.subTest(box=box), self.assertRaises(ValueError):
                jev.image_asset(original, box)


if __name__ == "__main__":
    unittest.main()
