"""Outcome tests: no GPU, network, vendor execution or downloaded fonts."""
from __future__ import annotations

import copy
from email.message import Message
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse
from urllib.response import addinfourl

from PIL import Image, ImageChops, ImageFont

from src.bubble_renderer import render_bubbles, wrap_text
from src.comfy_client import ComfyClient, ComfyError, build_workflow, output_node_id, render_episode
from src.script_formatter import format_script, parse_script
from src.webtoon_stitcher import stitch_episode


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


class FilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="factory-test-", dir=Path(__file__).resolve().parents[1])
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)


class FormatterTests(FilesTest):
    def test_formatter_does_not_overwrite_hand_edited_chunk(self):
        source = write_json(self.root / "input.json", {"cuts": [{"id": "cut_1", "description": "test"}]})
        output = self.root / "chunks"
        index = format_script(source, output)
        native = output / index["batches"][0]["text"]
        native.write_text("hand edited direction", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "modified"):
            format_script(source, output)
        self.assertEqual(native.read_text(), "hand edited direction")

    def test_explicit_page_capacity_and_multiple_speakers(self):
        parsed = parse_script('민「안녕」 준「반가워」')
        self.assertEqual([d["position"] for d in parsed["cuts"][0]["dialogue"]], ["auto", "auto"])
        render_bubbles(Image.new("RGB", (800, 650), "gray"), parsed["cuts"][0]["dialogue"])
        source = write_json(self.root / "input.json", {"cuts": [
            {"id": f"cut_{i}", "page": 1, "description": "한 페이지"} for i in range(6)]})
        with self.assertRaises(ValueError):
            format_script(source, self.root / "out", cuts_per_page=4)

    def test_five_pages_become_two_two_one_without_loss(self):
        episode = {"title": "분할 검증", "cuts": [
            {"id": f"cut_{i:03}", "page": i, "description": f"장면 {i}",
             "camera": {"shot": "CU", "angle": "low-angle", "lens": "85mm", "position": "profile"},
             "dialogue": [{"speaker": "민", "text": f"대사 {i}", "position": "top-left", "type": "normal"}],
             "image": f"../art/{i}.png", "gap_after": 135}
            for i in range(1, 6)]}
        source = write_json(self.root / "input" / "episode.json", episode)
        dest = self.root / "formatted"
        format_script(source, dest)
        normalized = json.loads((dest / "episode.json").read_text(encoding="utf-8"))
        self.assertEqual([x["id"] for x in normalized["cuts"]], [x["id"] for x in episode["cuts"]])
        self.assertEqual([x["page"] for x in normalized["cuts"]], [1, 2, 3, 4, 5])
        batches = sorted(dest.glob("chunk_*.txt"))
        self.assertEqual(len(batches), 3)
        for path, page_count in zip(batches, (2, 2, 1)):
            native = path.read_text(encoding="utf-8")
            self.assertIn("1P", native)
            self.assertEqual("2P" in native, page_count == 2)
            self.assertNotIn("3P", native)
            self.assertIn("タイトル", native)
        for original, cut in zip(episode["cuts"], normalized["cuts"]):
            self.assertEqual(cut["dialogue"], original["dialogue"])
            self.assertEqual(cut["camera"], original["camera"])
            self.assertEqual(cut["gap_after"], 135)
            self.assertEqual((dest / cut["image"]).resolve(), (source.parent / original["image"]).resolve())

    def test_plain_text_tagging_and_automatic_page_boundaries(self):
        result = parse_script("\ufeff[CU, low-angle, 85mm, profile] 첫 장면\n둘째 장면\n셋째 장면", cuts_per_page=2)
        cuts = result["cuts"]
        self.assertEqual(len(cuts), 3)
        self.assertEqual([c["page"] for c in cuts], [1, 1, 2])
        self.assertEqual(cuts[0]["camera"], {"shot": "CU", "angle": "low-angle", "lens": "85mm", "position": "profile"})
        self.assertTrue(all(len(c["camera"]) == 4 for c in cuts))
        self.assertIn("첫 장면", cuts[0]["description"])

    def test_empty_and_invalid_page_capacity_rejected(self):
        with self.assertRaises(ValueError):
            parse_script("  \n")
        with self.assertRaises(ValueError):
            parse_script("장면", cuts_per_page=0)

    def test_duplicate_id_in_json_rejected(self):
        cut = {"id": "same", "page": 1, "description": "장면"}
        source = write_json(self.root / "input.json", {"cuts": [cut, cut]})
        with self.assertRaises(ValueError):
            format_script(source, self.root / "formatted")


class LetteringTests(unittest.TestCase):
    def test_per_entry_font_size_changes_sfx_instead_of_silently_using_global_size(self):
        base = Image.new('RGB', (800, 500), 'white')
        small = render_bubbles(base, [{'text': '톡', 'type': 'sfx', 'box': [.1, .1, .6, .6], 'font_size': 24}], font_size=24)
        large = render_bubbles(base, [{'text': '톡', 'type': 'sfx', 'box': [.1, .1, .6, .6], 'font_size': 64}], font_size=24)
        self.assertNotEqual(small.tobytes(), large.tobytes())
        with self.assertRaises(ValueError):
            render_bubbles(base, [{'text': '톡', 'font_size': True}])

    def test_korean_wrap_preserves_every_character_and_newlines(self):
        font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 28) if Path("C:/Windows/Fonts/malgun.ttf").exists() else None
        if font is None:
            from src.bubble_renderer import _load_font
            font = _load_font(None, 28, "한글")
        text = "가나다라마바사아자차카타파하\n두번째줄"
        lines = wrap_text(text, font, 95)
        self.assertEqual("".join(lines), text.replace("\n", ""))
        self.assertTrue(all(font.getlength(line) <= 95 for line in lines))
        self.assertIn("두", "".join(lines))

    def test_each_balloon_kind_renders_and_preserves_original(self):
        original = Image.new("RGB", (800, 650), "#90b0a0")
        unchanged = original.copy()
        for kind in ("normal", "shout", "thought", "narration", "sfx"):
            with self.subTest(kind=kind):
                result = render_bubbles(original, [{"text": "한글 대사\n두 번째 줄", "type": kind,
                                                    "box": [0.05, 0.05, 0.75, 0.45]}])
                self.assertEqual(result.size, original.size)
                self.assertIsNotNone(ImageChops.difference(result.convert("RGB"), original).getbbox())
                self.assertIsNone(ImageChops.difference(original, unchanged).getbbox())
                self.assertEqual(result.convert("RGB").getpixel((799, 649)), original.getpixel((799, 649)))

    def test_invalid_font_overflow_and_overlap_fail_instead_of_dropping_text(self):
        art = Image.new("RGB", (800, 600), "gray")
        with self.assertRaises((ValueError, OSError)):
            render_bubbles(art, [{"text": "한글"}], font_path="missing-font.ttf")
        with self.assertRaises(ValueError):
            render_bubbles(art, [{"text": "긴대사" * 200, "box": [0.01, 0.01, 0.1, 0.1]}])
        with self.assertRaises(ValueError):
            render_bubbles(art, [{"text": "첫 대사", "box": [0.1, 0.1, 0.5, 0.4]},
                                {"text": "겹친 대사", "box": [0.1, 0.1, 0.5, 0.4]}])


class StitchTests(FilesTest):
    def test_authored_matte_and_fade_gutter(self):
        source = self.manifest(2)
        data = json.loads(source.read_text(encoding='utf-8'))
        data['cuts'][0].update(gap_after=30, gap_gradient_after=['#FFFFFF','#071523'])
        Image.new('RGBA',(80,40),(0,0,0,0)).save(self.root/'transparent.png')
        data['cuts'][1].update(image='transparent.png',matte='#071523')
        write_json(source,data)
        record_path = stitch_episode(source,self.root/'fade',top_padding=0,bottom_padding=0)
        record = json.loads(record_path.read_text(encoding='utf-8'))
        with Image.open(record_path.parent/'full_strip.png') as im:
            self.assertEqual(im.getpixel((0,400)),(255,255,255))
            self.assertEqual(im.getpixel((0,429)),(7,21,35))
            self.assertEqual(im.getpixel((0,430)),(7,21,35))
        data['cuts'][0]['gap_gradient_after']=['#FFFFFF']
        write_json(source,data)
        with self.assertRaisesRegex(ValueError,'two colors'):
            stitch_episode(source,self.root/'bad-fade')

    def test_inset_panel_width_placement_and_bounds(self):
        source = self.manifest(1)
        data = json.loads(source.read_text(encoding='utf-8'))
        data['cuts'][0].update(display_width=600, x=160)
        write_json(source, data)
        path = stitch_episode(source, self.root/'inset', top_padding=0, bottom_padding=0)
        record = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual((record['cuts'][0]['x'], record['cuts'][0]['width'], record['cuts'][0]['height']), (160,600,300))
        with Image.open(path.parent/'full_strip.png') as im:
            self.assertEqual(im.getpixel((159,100)), (255,255,255))
            self.assertEqual(im.getpixel((160,100)), (120,30,90))
            self.assertEqual(im.getpixel((760,100)), (255,255,255))
        data['cuts'][0]['x']=201
        write_json(source, data)
        with self.assertRaisesRegex(ValueError,'canvas width'):
            stitch_episode(source,self.root/'invalid-inset')

    def manifest(self, count=2):
        cuts = []
        for index in range(count):
            image = self.root / f"cut_{index}.png"
            Image.new("RGB", (400, 200 + index * 50), (120, 30 + index * 20, 90)).save(image)
            cuts.append({"id": f"cut_{index}", "image": image.name, "dialogue": []})
        return write_json(self.root / "input.json", {"title": "병합 테스트", "cuts": cuts})

    def test_dimensions_gutters_order_and_lossless_slice_reconstruction(self):
        source = self.manifest()
        record_path = stitch_episode(source, self.root / "output", padding=75, top_padding=20,
                                     bottom_padding=30, max_height=700)
        record = json.loads(record_path.read_text(encoding="utf-8"))
        with Image.open(record_path.parent / "full_strip.png") as full:
            self.assertEqual(full.size, (800, 20 + 400 + 75 + 500 + 30))
            self.assertEqual(full.getpixel((50, 419)), (120, 30, 90))
            self.assertEqual(full.getpixel((50, 420)), (255, 255, 255))
            self.assertEqual(full.getpixel((50, 494)), (255, 255, 255))
            self.assertEqual(full.getpixel((50, 495)), (120, 50, 90))
            restored = Image.new("RGB", full.size)
            offset = 0
            for part in record["parts"]:
                with Image.open(record_path.parent / part["path"]) as segment:
                    self.assertEqual(segment.width, 800)
                    self.assertLessEqual(segment.height, 700)
                    self.assertEqual(part["y"], offset)
                    restored.paste(segment, (0, offset))
                    offset += segment.height
            self.assertEqual(offset, full.height)
            self.assertIsNone(ImageChops.difference(full, restored).getbbox())

    def test_missing_art_no_partial_deliverable_and_memory_limit(self):
        source = write_json(self.root / "input.json", {"cuts": [{"id": "missing", "image": "missing.png"}]})
        with self.assertRaises(OSError):
            stitch_episode(source, self.root / "output")
        self.assertFalse((self.root / "output" / "manifest.json").exists())
        source = self.manifest()
        with self.assertRaisesRegex(ValueError, "pixels"):
            stitch_episode(source, self.root / "output", max_pixels=100)

    def test_rerun_protection_and_stale_part_cleanup(self):
        source = self.manifest(3)
        output = self.root / "out"
        stitch_episode(source, output, max_height=700)
        old_parts = set(output.glob("slice_*.png"))
        with self.assertRaises(FileExistsError):
            stitch_episode(source, output)
        source = self.manifest(1)
        stitch_episode(source, output, max_height=1280, overwrite=True)
        self.assertEqual(len(list(output.glob("slice_*.png"))), 1)
        self.assertTrue(any(not p.exists() for p in old_parts))

    def test_smart_boundaries_keep_whole_cuts_and_reject_taller_than_limit(self):
        source = self.manifest(3)
        path = stitch_episode(source, self.root / "smart", max_height=750)
        data = json.loads(path.read_text(encoding="utf-8"))
        for part in data["parts"][:-1]:
            boundary = part["y"] + part["height"]
            self.assertFalse(any(c["y"] < boundary < c["y"] + c["height"] for c in data["cuts"]))
        with self.assertRaisesRegex(ValueError, "never sliced"):
            stitch_episode(source, self.root / "too_short", max_height=300)
        self.assertFalse((self.root / "too_short" / "manifest.json").exists())

    def test_configurable_width_black_gutter_and_modified_output_protection(self):
        source = self.manifest(1)
        data = json.loads(source.read_text(encoding="utf-8"))
        data["cuts"][0]["id"] = "scene.001"
        write_json(source, data)
        path = stitch_episode(source, self.root / "black", width=600, background="#000000")
        data = json.loads(path.read_text(encoding="utf-8"))
        full_path = path.parent / data["full"]["path"]
        with Image.open(full_path) as image:
            self.assertEqual(image.width, 600)
            self.assertEqual(image.getpixel((0, 0)), (0, 0, 0))
        full_path.write_bytes(b"user edit")
        with self.assertRaisesRegex(ValueError, "modified"):
            stitch_episode(source, path.parent, overwrite=True)
        self.assertEqual(full_path.read_bytes(), b"user edit")

    def test_forged_manifest_does_not_delete_unowned_file(self):
        source = self.manifest(1)
        output = self.root / "forged"
        victim = output / "slice_999.png"
        victim.parent.mkdir()
        victim.write_bytes(b"private art")
        write_json(output / "manifest.json", {"generator": "webtoon-factory", "schema_version": 1,
                                              "full": {"path": victim.name}, "parts": []})
        with self.assertRaises(ValueError):
            stitch_episode(source, output, overwrite=True)
        self.assertEqual(victim.read_bytes(), b"private art")


class Response:
    def __init__(self, data):
        self.data = json.dumps(data).encode() if isinstance(data, dict) else data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size=-1):
        return self.data if size < 0 else self.data[:size]


class FakeComfyAPI:
    """HTTP protocol fixture passed into the real urllib-based client."""
    def __init__(self, graph):
        self.calls = []
        self.graph = graph
        self.queued = {}
        self.polls = {}
        buffer = io.BytesIO()
        Image.new("RGB", (768, 1024), "#8cafa1").save(buffer, format="PNG")
        self.png = buffer.getvalue()
        self.info = {node["class_type"]: {"input": {"required": {}}} for node in graph.values()}
        choices = {"CheckpointLoaderSimple": {"ckpt_name": [["base.safetensors"]]},
                   "LoraLoader": {"lora_name": [["min.safetensors"]]},
                   "ControlNetLoader": {"control_net_name": [["pose.safetensors", "line.safetensors"]]},
                   "KSampler": {"sampler_name": [["euler"]], "scheduler": [["normal"]]}}
        for kind, specs in choices.items():
            if kind in self.info:
                self.info[kind]["input"]["required"] = specs

    def __call__(self, request, timeout):
        self.calls.append((request.get_method(), request.full_url, request.data, timeout))
        url = urllib.parse.urlsplit(request.full_url)
        if url.path == "/object_info":
            return Response(self.info)
        if url.path == "/upload/image":
            if b"\x89PNG" not in request.data or b'name="image"' not in request.data:
                raise AssertionError("Guide must be uploaded as multipart image bytes")
            return Response({"name": "server-renamed.png", "subfolder": "webtoon_factory", "type": "input"})
        if url.path == "/prompt":
            prompt_id = f"job-{len(self.queued)+1}"
            self.queued[prompt_id] = json.loads(request.data)["prompt"]
            return Response({"prompt_id": prompt_id, "node_errors": {}})
        if url.path.startswith("/history/"):
            prompt_id = url.path.rsplit("/", 1)[-1]
            self.polls[prompt_id] = self.polls.get(prompt_id, 0) + 1
            if self.polls[prompt_id] == 1:
                return Response({})
            node = output_node_id(self.queued[prompt_id])
            return Response({prompt_id: {"status": {"completed": True, "status_str": "success"},
                                        "outputs": {"unrelated": {"images": [{"filename": "preview.png"}]},
                                                    node: {"images": [{"filename": "cut.png", "type": "output"}]}}}})
        if url.path == "/view":
            if urllib.parse.parse_qs(url.query).get("filename") != ["cut.png"]:
                raise AssertionError("Client selected an unrelated preview output")
            return Response(self.png)
        raise AssertionError(f"Unexpected HTTP endpoint: {url.path}")


class ComfyTests(FilesTest):
    def setUp(self):
        super().setUp()
        self.config = {"checkpoint": "base.safetensors", "model_family": "sdxl", "width": 768, "height": 1024}
        self.characters = {"characters": {"min": {"triggers": "min_identity", "lora": "min.safetensors", "strength": 0.75}}}
        self.cut = {"id": "cut_001", "page": 1, "description": "test pose", "characters": ["min"],
                    "controls": [{"image": "guide.png", "model": "pose.safetensors"},
                                 {"image": "background.png", "model": "line.safetensors", "strength": 0.6}],
                    "dialogue": [{"text": "검증 완료", "type": "narration", "position": "top"}]}
        Image.new("RGB", (384, 512), "white").save(self.root / "guide.png")
        Image.new("RGB", (768, 1024), "black").save(self.root / "background.png")
        self.source = write_json(self.root / "episode.json", {"cuts": [self.cut]})

    def test_default_transport_rejects_cross_origin_redirect(self):
        headers = Message()
        headers["Location"] = "http://comfy.example.invalid/object_info"
        response = addinfourl(io.BytesIO(b""), headers, "http://127.0.0.1:8188/object_info", 302)
        response.msg = "Found"
        with patch("urllib.request.HTTPHandler.http_open", return_value=response) as transport:
            with self.assertRaisesRegex(ComfyError, "HTTP 302"):
                ComfyClient()._json("/object_info")
        transport.assert_called_once()

    def test_legacy_render_requires_opt_in_for_remote_config(self):
        config = {**self.config, "server": "https://comfy.example.invalid", "allow_remote": True}
        with patch("urllib.request.HTTPHandler.http_open") as http:
            with patch("urllib.request.HTTPSHandler.https_open") as https:
                with self.assertRaisesRegex(ValueError, "allow-remote"):
                    render_episode(self.source, self.characters, config, self.root / "remote", check=True)
        http.assert_not_called()
        https.assert_not_called()

    def test_lora_and_both_controlnets_chain_into_sampler(self):
        graph = build_workflow(self.cut, self.characters, self.config)
        kinds = [n["class_type"] for n in graph.values()]
        self.assertEqual(kinds.count("LoraLoader"), 1)
        self.assertEqual(kinds.count("ControlNetApplyAdvanced"), 2)
        positive = [n["inputs"]["text"] for n in graph.values() if n["class_type"] == "CLIPTextEncode"]
        self.assertTrue(any("min_identity" in text for text in positive))
        sampler = next(n for n in graph.values() if n["class_type"] == "KSampler")
        control_id = sampler["inputs"]["positive"][0]
        self.assertEqual(graph[control_id]["class_type"], "ControlNetApplyAdvanced")
        prior_id = graph[control_id]["inputs"]["positive"][0]
        self.assertEqual(graph[prior_id]["class_type"], "ControlNetApplyAdvanced")
        family_mismatch = copy.deepcopy(self.characters)
        family_mismatch["characters"]["min"]["model_family"] = "sd15"
        with self.assertRaises(ValueError):
            build_workflow(self.cut, family_mismatch, self.config)

    def test_dry_run_writes_workflows_but_no_images_or_network_requests(self):
        output = self.root / "dry"
        with patch("urllib.request.urlopen", side_effect=AssertionError("dry-run made a network request")):
            result = render_episode(self.source, self.characters, self.config, output, dry_run=True)
        self.assertEqual(result["status"], "dry_run_not_rendered")
        self.assertEqual(len(list((output / "workflows").glob("*.json"))), 1)
        self.assertFalse(list(output.glob("*.png")))
        self.assertFalse((output / "episode.rendered.json").exists())
        self.assertEqual(len(result["cuts"][0]["uploads"]), 2)

    def test_actual_client_upload_queue_poll_download_and_stitch_with_protocol_fixture(self):
        graph = build_workflow(self.cut, self.characters, self.config)
        api = FakeComfyAPI(graph)
        client = ComfyClient(opener=api, sleeper=lambda _: None)
        output = self.root / "renders"
        result = render_episode(self.source, self.characters, self.config, output, client=client)
        self.assertEqual(result["status"], "rendered")
        rendered = Path(result["rendered_manifest"])
        self.assertTrue(rendered.is_file())
        manifest = json.loads(rendered.read_text(encoding="utf-8"))
        self.assertTrue((rendered.parent / manifest["cuts"][0]["image"]).is_file())
        self.assertEqual(sum(method == "POST" and "/prompt" in url for method, url, _, _ in api.calls), 1)
        self.assertEqual(sum("/upload/image" in url for _, url, _, _ in api.calls), 2)
        self.assertTrue(all(0 < timeout <= 30 for _, _, _, timeout in api.calls))
        queued = next(iter(api.queued.values()))
        self.assertTrue(all(n["inputs"]["image"] == "webtoon_factory/server-renamed.png"
                            for n in queued.values() if n["class_type"] == "LoadImage"))
        final = stitch_episode(rendered, self.root / "webtoon")
        self.assertTrue(final.is_file())

    def test_missing_model_and_node_errors_do_not_queue_or_report_success(self):
        graph = build_workflow(self.cut, self.characters, self.config)
        api = FakeComfyAPI(graph)
        api.info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"] = [["other.safetensors"]]
        with self.assertRaisesRegex(ComfyError, "unavailable"):
            render_episode(self.source, self.characters, self.config, self.root / "bad", client=ComfyClient(opener=api))
        self.assertTrue(all(method == "GET" for method, _, _, _ in api.calls))
        client = ComfyClient(opener=lambda request, **_: Response({"prompt_id": "bad", "node_errors": {"1": "invalid"}}))
        with self.assertRaises(ComfyError):
            client.queue(graph)

    def test_execution_failure_timeout_and_no_automatic_post_retry(self):
        failure = {"job": {"status": {"messages": [["execution_error", {"exception_message": "out of memory"}]]}}}
        client = ComfyClient(opener=lambda request, **_: Response(failure))
        with self.assertRaisesRegex(ComfyError, "execution failed"):
            client.wait("job", "9")
        clock = [0.0]
        def sleep(seconds):
            clock[0] += seconds
        client = ComfyClient(timeout=0.03, poll_interval=0.01, opener=lambda request, **_: Response({}),
                             clock=lambda: clock[0], sleeper=sleep)
        with self.assertRaises(TimeoutError):
            client.wait("job", "9")
        opener = unittest.mock.Mock(side_effect=urllib.error.URLError("connection lost"))
        with self.assertRaisesRegex(ComfyError, "not retried"):
            ComfyClient(opener=opener).queue({})
        self.assertEqual(opener.call_count, 1)

    def test_mismatched_guide_aspect_rejected_before_http(self):
        Image.new("RGB", (512, 512), "white").save(self.root / "guide.png")
        with patch("urllib.request.urlopen", side_effect=AssertionError("validation must precede network")):
            with self.assertRaisesRegex(ValueError, "aspect"):
                render_episode(self.source, self.characters, self.config, self.root / "bad-guide")

    def test_base_workflow_json_is_loaded_and_injected_without_discarding_metadata(self):
        base = json.loads((Path(__file__).resolve().parents[1] / "workspace" / "workflow_api.example.json").read_text())
        base["1"]["_meta"] = {"title": "retained node metadata"}
        template = write_json(self.root / "workflow.json", base)
        result = render_episode(self.source, self.characters, self.config, self.root / "template-dry",
                                dry_run=True, workflow_template=template)
        graph = result["cuts"][0]["workflow"]
        self.assertEqual(graph["1"]["_meta"], base["1"]["_meta"])
        self.assertEqual(graph["1"]["inputs"]["ckpt_name"], "base.safetensors")
        text = " ".join(n["inputs"].get("text", "") for n in graph.values())
        self.assertIn("min_identity", text)
        self.assertIn("clean lineart", text)
        self.assertEqual(sum(n["class_type"] == "ControlNetApplyAdvanced" for n in graph.values()), 2)
        base["extra"] = {"class_type": "UnknownCustomNode", "inputs": {}}
        with self.assertRaises(ValueError):
            render_episode(self.source, self.characters, self.config, self.root / "unsupported",
                           dry_run=True, workflow_template=base)


class TenCutPipelineTests(FilesTest):
    def test_demo_refuses_escaped_path_before_overwriting_any_art(self):
        from src.demo import run_demo
        example = json.loads((Path(__file__).resolve().parents[1] / "workspace" / "01_scripts" / "example.json").read_text(encoding="utf-8"))
        workspace = self.root / "workspace"
        example["cuts"][0]["image"] = "../../important.png"
        write_json(workspace / "01_scripts" / "example.json", example)
        important = self.root / "important.png"
        important.write_bytes(b"original art must survive")
        with self.assertRaises(ValueError):
            run_demo(workspace, overwrite=True)
        self.assertEqual(important.read_bytes(), b"original art must survive")

    def test_ten_mock_trios_two_chunks_korean_webtoon_artifacts(self):
        cuts = []
        for i in range(10):
            # Each cut has a mock atari, background and art; no GPU required.
            for role, color in (("atari", "white"), ("background", "#dddddd"), ("art", "#9db6ab")):
                path = self.root / role / f"{i}.png"
                path.parent.mkdir(exist_ok=True)
                Image.new("RGB", (384, 512), color).save(path)
                self.assertGreater(path.stat().st_size, 0)
            cuts.append({"id": f"cut_{i:03d}", "description": f"테스트 장면 {i}",
                         "atari": f"atari/{i}.png", "background": f"background/{i}.png", "image": f"art/{i}.png",
                         "dialogue": [{"speaker": "테스트", "text": f"{i+1}번째 컷입니다.", "position": "auto"}]})
        source = write_json(self.root / "ten.json", {"title": "열 컷 통합 검증", "cuts": cuts})
        formatted = self.root / "chunks"
        index = format_script(source, formatted, cuts_per_page=4)
        self.assertEqual([b["page_count"] for b in index["batches"]], [2, 1])
        self.assertEqual([len(b["cut_ids"]) for b in index["batches"]], [8, 2])
        final = stitch_episode(formatted / "episode.json", self.root / "output")
        data = json.loads(final.read_text(encoding="utf-8"))
        self.assertEqual(len(data["cuts"]), 10)
        self.assertGreater(len(data["parts"]), 1)
        for record in [data["full"], *data["parts"]]:
            path = final.parent / record["path"]
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 0)
            with Image.open(path) as image:
                self.assertEqual(image.width, 800)
                self.assertGreater(image.height, 0)


if __name__ == "__main__":
    unittest.main()
