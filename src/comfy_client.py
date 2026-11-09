"""Small ComfyUI SD1.5/SDXL checkpoint client for explicitly authored cuts.

Adapted from ahmet360/manga-studio: comfy_workflow.py (core checkpoint,
LoRA and sampling graph) and generate.py (HTTP queue/history/view/upload).
https://github.com/ahmet360/manga-studio
The original's page generation, custom-node pipelines and automatic prompts
are intentionally outside this module. Control images must already be in the
format expected by the selected ControlNet; a mannequin is not an OpenPose map.

Upstream MIT License, Copyright (c) 2026 ahmet360
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import ipaddress
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from PIL import Image, ImageOps


class ComfyError(RuntimeError):
    """A rejected workflow, inaccessible server, or failed render."""


def load_json(path: str | Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _number(value, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    value = float(value)
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum:g} and {maximum:g}")
    return value


def _integer(value, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be an integer")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{name} must be a finite integer")
    if int(value) != value or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}")
    return int(value)


def _text(value, name: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{name} must be {'a' if allow_empty else 'a nonempty'} string")
    return value.strip()


def _character_map(characters: dict) -> dict:
    entries = characters.get("characters", characters)
    if not isinstance(entries, dict):
        raise ValueError("characters must be an object keyed by character name")
    return entries


def _controls(cut: dict, config: dict) -> list[dict]:
    """Explicit per-cut controls replace defaults; atari/background add guides."""
    controls = cut.get("controls", config.get("controls", []))
    if not isinstance(controls, list) or any(not isinstance(c, dict) for c in controls):
        raise ValueError("controls must be an array of {image, model, ...} objects")
    result = [dict(c) for c in controls]
    settings = config.get("controlnet", {})
    if not isinstance(settings, dict):
        raise ValueError("controlnet must be an object")
    for role in ("atari", "background"):
        if cut.get(role):
            entry = settings.get(role)
            if not isinstance(entry, dict) or not entry.get("model"):
                raise ValueError(
                    f"cut {cut.get('id')}: {role} requires controlnet.{role}.model; "
                    "supply a preprocessed guide compatible with that model"
                )
            result.append({**entry, "image": cut[role], "role": role})
    for item in result:
        item["image"] = _text(item.get("image"), "control image")
        item["model"] = _text(item.get("model"), "ControlNet model")
        item["strength"] = _number(item.get("strength", 0.8), "control strength", 0, 10)
        item["start_percent"] = _number(item.get("start_percent", 0), "start_percent", 0, 1)
        item["end_percent"] = _number(item.get("end_percent", 1), "end_percent", 0, 1)
        if item["start_percent"] >= item["end_percent"]:
            raise ValueError("control start_percent must be smaller than end_percent")
        family = item.get("model_family")
        if family and family != config.get("model_family", "sdxl"):
            raise ValueError("ControlNet model_family differs from checkpoint model_family")
    return result


def _template_bindings(template: dict) -> dict[str, str]:
    """Recognize a seven-node API base, rejecting every unsupported extension."""
    error = ("--workflow requires a plain seven-node API JSON base: checkpoint, two text encoders, "
             "empty latent (batch_size=1), KSampler, VAE decode, SaveImage. "
             "Export API format, remove LoRA/ControlNet/custom nodes from the base; "
             "the factory injects those from characters.json and cut guides.")
    if not isinstance(template, dict) or len(template) != 7:
        raise ValueError(error)
    fields = {
        "CheckpointLoaderSimple": {"ckpt_name"},
        "CLIPTextEncode": {"text", "clip"},
        "EmptyLatentImage": {"width", "height", "batch_size"},
        "KSampler": {"seed", "steps", "cfg", "sampler_name", "scheduler", "denoise",
                     "model", "positive", "negative", "latent_image"},
        "VAEDecode": {"samples", "vae"},
        "SaveImage": {"images", "filename_prefix"},
    }
    by_kind = {}
    for node_id, node in template.items():
        if (not isinstance(node_id, str) or not isinstance(node, dict) or
                set(node) - {"class_type", "inputs", "_meta"} or
                node.get("class_type") not in fields or not isinstance(node.get("inputs"), dict)):
            raise ValueError(error + f" Unsupported node: {node_id!r}")
        kind = node["class_type"]
        if set(node["inputs"]) != fields[kind]:
            raise ValueError(error + f" Unexpected/missing inputs on node {node_id!r} ({kind}).")
        by_kind.setdefault(kind, []).append(node_id)
    if any(len(by_kind.get(kind, [])) != (2 if kind == "CLIPTextEncode" else 1) for kind in fields):
        raise ValueError(error)
    bindings = {kind: ids[0] for kind, ids in by_kind.items() if kind != "CLIPTextEncode"}
    sampler = template[bindings["KSampler"]]["inputs"]
    ckpt = bindings["CheckpointLoaderSimple"]
    latent = bindings["EmptyLatentImage"]
    decode = bindings["VAEDecode"]
    for role in ("positive", "negative"):
        link = sampler[role]
        if (not isinstance(link, list) or len(link) != 2 or link[1] != 0 or
                link[0] not in by_kind["CLIPTextEncode"]):
            raise ValueError(error + f" Invalid {role} encoder binding.")
        bindings[role] = link[0]
    if bindings["positive"] == bindings["negative"]:
        raise ValueError(error + " Positive and negative must be distinct text encoders.")
    expected = {
        bindings["positive"]: {"clip": [ckpt, 1]},
        bindings["negative"]: {"clip": [ckpt, 1]},
        bindings["KSampler"]: {"model": [ckpt, 0], "latent_image": [latent, 0]},
        decode: {"samples": [bindings["KSampler"], 0], "vae": [ckpt, 2]},
        bindings["SaveImage"]: {"images": [decode, 0]},
    }
    for node_id, links in expected.items():
        if any(template[node_id]["inputs"][field] != link for field, link in links.items()):
            raise ValueError(error + f" Unsupported links on node {node_id!r}.")
    if template[latent]["inputs"]["batch_size"] != 1:
        raise ValueError(error + " batch_size must equal 1.")
    return bindings


def _template_config(template: dict, config: dict, bindings: dict) -> dict:
    sampler = template[bindings["KSampler"]]["inputs"]
    latent = template[bindings["EmptyLatentImage"]]["inputs"]
    settings = {"checkpoint": template[bindings["CheckpointLoaderSimple"]]["inputs"]["ckpt_name"],
                "width": latent["width"], "height": latent["height"]}
    settings.update({key: sampler[key] for key in ("seed", "steps", "cfg", "sampler_name", "scheduler", "denoise")})
    settings.update(config)
    for role, key in (("positive", "prompt_prefix"), ("negative", "negative_prompt")):
        base_text = _text(template[bindings[role]]["inputs"]["text"], f"template {role} text", True)
        configured = _text(config.get(key, ""), key, True)
        settings[key] = ", ".join(part for part in (base_text, configured) if part)
    return settings


def _merge_template(graph: dict, template: dict, bindings: dict) -> dict:
    """Keep base IDs/metadata and append only factory-authored conditioning nodes."""
    rename = {}
    encoders = [key for key, node in graph.items() if node["class_type"] == "CLIPTextEncode"]
    rename[encoders[0]], rename[encoders[1]] = bindings["positive"], bindings["negative"]
    used = set(template)
    counter = 0
    for node_id, node in graph.items():
        kind = node["class_type"]
        if kind != "CLIPTextEncode" and kind in bindings:
            rename[node_id] = bindings[kind]
        elif node_id not in rename:
            while True:
                counter += 1
                new_id = f"factory_{counter}"
                if new_id not in used:
                    break
            rename[node_id] = new_id
            used.add(new_id)
    result = copy.deepcopy(template)
    for node_id, node in graph.items():
        new_node = copy.deepcopy(node)
        for field, value in new_node["inputs"].items():
            if isinstance(value, list):
                new_node["inputs"][field] = [rename[value[0]], value[1]]
        new_id = rename[node_id]
        if new_id in template and "_meta" in template[new_id]:
            new_node["_meta"] = copy.deepcopy(template[new_id]["_meta"])
        result[new_id] = new_node
    return result


def build_workflow(cut: dict, characters: dict, config: dict,
                   uploaded_images: dict[str, str] | None = None, *,
                   workflow_template: dict | None = None) -> dict:
    """Build a core-node API graph, without network access or vendor imports.

    uploaded_images maps authored guide paths to ComfyUI input image names.
    Without that map, LoadImage contains the authored path; plan_episode replaces
    those values with explicit upload destinations before saving a dry-run graph.
    model_family is a user's compatibility declaration, not model-file detection.
    A template is a restricted seven-node API base. Its model/sampling settings
    are defaults; explicit config keys override them. Its text is a shared prefix.
    Base IDs/_meta survive; extra/custom graph nodes are rejected, not discarded.
    """
    if workflow_template is not None:
        bindings = _template_bindings(workflow_template)
        effective = _template_config(workflow_template, config, bindings)
        graph = build_workflow(cut, characters, effective, uploaded_images)
        return _merge_template(graph, workflow_template, bindings)
    family = config.get("model_family", "sdxl")
    if family not in {"sd15", "sdxl"}:
        raise ValueError("model_family must be sd15 or sdxl; Flux/Anima are unsupported")
    checkpoint = _text(config.get("checkpoint"), "checkpoint")
    width = _integer(config.get("width", 768), "width", 64, 4096)
    height = _integer(config.get("height", 1024), "height", 64, 4096)
    if width % 8 or height % 8:
        raise ValueError("render width and height must be multiples of 8")
    seed = _integer(cut.get("seed", config.get("seed", 42)), "seed", 0, 2**64 - 1)
    steps = _integer(config.get("steps", 24), "steps", 1, 10000)
    cfg = _number(config.get("cfg", 6.5), "cfg", 0, 100)
    entries = _character_map(characters)
    names = cut.get("characters", [])
    if not isinstance(names, list) or any(not isinstance(n, str) for n in names):
        raise ValueError("cut.characters must be an array of names")
    if len(set(names)) != len(names):
        raise ValueError("cut.characters must not repeat the same character")
    graph = {}

    def add(class_type: str, inputs: dict) -> str:
        node_id = str(len(graph) + 1)
        graph[node_id] = {"class_type": class_type, "inputs": inputs}
        return node_id

    ckpt = add("CheckpointLoaderSimple", {"ckpt_name": checkpoint})
    model, clip = [ckpt, 0], [ckpt, 1]
    positive = [_text(config.get("prompt_prefix", ""), "prompt_prefix", True)]
    negatives = [_text(config.get("negative_prompt", ""), "negative_prompt", True)]
    for name in names:
        if name not in entries or not isinstance(entries[name], dict):
            raise ValueError(f"character {name!r} has no characters.json record")
        char = entries[name]
        if char.get("model_family") and char["model_family"] != family:
            raise ValueError(f"character {name!r}: LoRA model_family differs from checkpoint")
        trigger = char.get("triggers", char.get("trigger", ""))
        positive.append(_text(trigger, f"{name}.triggers", True))
        if char.get("negative"):
            negatives.append(_text(char["negative"], f"{name}.negative"))
        if char.get("lora"):
            strength = _number(char.get("strength", 0.8), f"{name}.strength", -20, 20)
            lora = add("LoraLoader", {
                "lora_name": _text(char["lora"], f"{name}.lora"),
                "strength_model": strength,
                "strength_clip": _number(char.get("strength_clip", strength),
                                         f"{name}.strength_clip", -20, 20),
                "model": model, "clip": clip,
            })
            model, clip = [lora, 0], [lora, 1]
    positive.append(_text(cut.get("prompt") or cut.get("description"), "cut prompt/description"))
    camera = cut.get("camera", {})
    if not isinstance(camera, dict):
        raise ValueError("cut.camera must be an object")
    for key in ("shot", "angle", "lens", "position"):
        if camera.get(key):
            positive.append(_text(camera[key], f"camera.{key}"))
    positive.append(_text(config.get("prompt_suffix", ""), "prompt_suffix", True))
    if cut.get("negative_prompt"):
        negatives.append(_text(cut["negative_prompt"], "cut.negative_prompt"))
    pos = [add("CLIPTextEncode", {"clip": clip, "text": ", ".join(p for p in positive if p)}), 0]
    neg = [add("CLIPTextEncode", {"clip": clip, "text": ", ".join(p for p in negatives if p)}), 0]
    for control in _controls(cut, config):
        control_net = add("ControlNetLoader", {"control_net_name": control["model"]})
        image_name = (uploaded_images or {}).get(control["image"], control["image"])
        image_node = add("LoadImage", {"image": image_name})
        applied = add("ControlNetApplyAdvanced", {
            "positive": pos, "negative": neg, "control_net": [control_net, 0],
            "image": [image_node, 0], "strength": control["strength"],
            "start_percent": control["start_percent"], "end_percent": control["end_percent"],
            "vae": [ckpt, 2],
        })
        pos, neg = [applied, 0], [applied, 1]
    latent = add("EmptyLatentImage", {"width": width, "height": height, "batch_size": 1})
    sampler = add("KSampler", {
        "model": model, "positive": pos, "negative": neg, "latent_image": [latent, 0],
        "seed": seed, "steps": steps, "cfg": cfg,
        "sampler_name": _text(config.get("sampler_name", "euler"), "sampler_name"),
        "scheduler": _text(config.get("scheduler", "normal"), "scheduler"),
        "denoise": _number(config.get("denoise", 1.0), "denoise", 0, 1),
    })
    decoded = add("VAEDecode", {"samples": [sampler, 0], "vae": [ckpt, 2]})
    add("SaveImage", {"images": [decoded, 0], "filename_prefix": "webtoon_factory/cut"})
    return graph


def output_node_id(workflow: dict) -> str:
    nodes = [key for key, node in workflow.items() if node.get("class_type") == "SaveImage"]
    if len(nodes) != 1:
        raise ValueError("workflow must have exactly one SaveImage output node")
    return nodes[0]


def is_loopback_host(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() == "localhost"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ComfyClient:
    """Standard-library transport. Each POST is attempted once, including uploads."""

    def __init__(self, server: str = "http://127.0.0.1:8188", timeout: float = 600,
                 http_timeout: float = 30, poll_interval: float = 1,
                 opener=None, sleeper=None, clock=None, *, allow_remote: bool = False):
        server = _text(server, "server")
        if any(ord(char) <= 32 for char in server):
            raise ValueError("server URL must not contain whitespace")
        if not server.startswith(("http://", "https://")):
            server = "http://" + server
        parsed = urllib.parse.urlsplit(server)
        if not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
            raise ValueError("server must be an HTTP(S) base URL without credentials/query/fragment")
        parsed.port
        if not allow_remote and not is_loopback_host(parsed.hostname):
            raise ValueError("non-loopback server requires explicit --allow-remote")
        self.base = server.rstrip("/")
        self.timeout = _number(timeout, "timeout", 0.01, 86400)
        self.http_timeout = _number(http_timeout, "http_timeout", 0.01, 300)
        self.poll_interval = _number(poll_interval, "poll_interval", 0.01, 60)
        self.client_id = str(uuid.uuid4())
        self._opener = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect()
        ).open
        self._sleep = sleeper or time.sleep
        self._clock = clock or time.monotonic

    def _request(self, path: str, data: bytes | None = None,
                 headers: dict | None = None, timeout: float | None = None) -> bytes:
        request = urllib.request.Request(self.base + path, data=data, headers=headers or {})
        try:
            with self._opener(request, timeout=min(timeout or self.http_timeout, self.http_timeout)) as response:
                payload = response.read(64 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as exc:
            # Error responses can contain prompts/paths; retain a bounded diagnostic.
            detail = exc.read(4096).decode("utf-8", "replace")
            raise ComfyError(f"ComfyUI {path.split('?')[0]} HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ComfyError(
                f"Cannot reach ComfyUI {self.base}{path.split('?')[0]}: {exc}. "
                "Check the server URL and that ComfyUI is running. POSTs are not retried."
            ) from exc
        if len(payload) > 64 * 1024 * 1024:
            raise ComfyError("ComfyUI response exceeded 64 MiB")
        return payload

    def _json(self, path: str, data: dict | None = None, timeout: float | None = None) -> dict:
        payload = None if data is None else json.dumps(data, allow_nan=False).encode("utf-8")
        body = self._request(path, payload, {"Content-Type": "application/json"} if payload else None, timeout)
        try:
            result = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ComfyError(f"ComfyUI {path} returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise ComfyError(f"ComfyUI {path} returned a non-object JSON response")
        return result

    def preflight(self, workflows: dict | list[dict]) -> dict:
        """Check required nodes and all known COMBO/model choices before any POST.

        This confirms installed filenames and graph surface only. It cannot prove
        a checkpoint/LoRA/ControlNet's architecture or visual quality.
        """
        info = self._json("/object_info")
        if isinstance(workflows, dict):
            workflows = [workflows]
        problems = set()
        for graph in workflows:
            for node in graph.values():
                kind = node["class_type"]
                if kind not in info:
                    problems.add(f"missing core node {kind}; update/check your ComfyUI installation")
                    continue
                schema = info[kind].get("input", {})
                specs = {**schema.get("required", {}), **schema.get("optional", {})}
                enum_fields = {"CheckpointLoaderSimple": "ckpt_name", "LoraLoader": "lora_name",
                               "ControlNetLoader": "control_net_name", "KSampler": "sampler_name"}
                expected_enums = {enum_fields[kind]} if kind in enum_fields else set()
                if kind == "KSampler":
                    expected_enums.add("scheduler")
                for field in expected_enums:
                    spec = specs.get(field)
                    if not isinstance(spec, (list, tuple)) or not spec or not (
                            isinstance(spec[0], list) or spec[0] == "COMBO"):
                        problems.add(f"{kind}.{field}: /object_info has no model/enum choices; check the server version")
                for field, value in node["inputs"].items():
                    if isinstance(value, list) or (kind == "LoadImage" and field == "image"):
                        continue
                    spec = specs.get(field)
                    if not spec:
                        # Optional VAE is absent on some older core versions.
                        if kind == "ControlNetApplyAdvanced" and field == "vae":
                            continue
                        continue
                    choices = None
                    if isinstance(spec[0], list):
                        choices = spec[0]
                    elif spec[0] == "COMBO" and len(spec) > 1 and isinstance(spec[1], dict):
                        choices = spec[1].get("options", [])
                    if choices is not None and value not in choices:
                        preview = ", ".join(map(str, choices[:8])) or "(none installed)"
                        problems.add(f"{kind}.{field}={value!r} is unavailable; choices: {preview}")
                    if spec[0] in ("INT", "FLOAT"):
                        bounds = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
                        validate = _integer if spec[0] == "INT" else _number
                        try:
                            validate(value, f"{kind}.{field}", bounds.get("min", -math.inf), bounds.get("max", math.inf))
                        except ValueError as exc:
                            problems.add(str(exc))
        if problems:
            raise ComfyError("ComfyUI preflight failed:\n- " + "\n- ".join(sorted(problems)) +
                             "\nInstall compatible models in ComfyUI, then use their exact listed filenames.")
        return {"status": "preflight_passed", "workflow_count": len(workflows),
                "model_compatibility": "declared_by_user_not_verified"}

    def upload_image(self, path: str | Path, name: str | None = None) -> str:
        path = Path(path)
        name = name or path.name
        if Path(name).name != name or any(ch in name for ch in '\r\n"'):
            raise ValueError("upload name must be a plain filename")
        data = path.read_bytes()
        if len(data) > 32 * 1024 * 1024:
            raise ValueError(f"guide is larger than 32 MiB: {path}")
        boundary = "webtoon-" + uuid.uuid4().hex
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        sections = [
            f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\nContent-Type: {content_type}\r\n\r\n'.encode(),
            data, b"\r\n",
        ]
        for key, value in (("type", "input"), ("subfolder", "webtoon_factory"), ("overwrite", "false")):
            sections.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        sections.append(f"--{boundary}--\r\n".encode())
        raw = self._request("/upload/image", b"".join(sections),
                            {"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            result = json.loads(raw)
            filename = _text(result["name"], "uploaded name")
            subfolder = result.get("subfolder", "")
        except (ValueError, KeyError, TypeError) as exc:
            raise ComfyError("ComfyUI upload response has no valid image name") from exc
        return f"{subfolder}/{filename}" if subfolder else filename

    def queue(self, workflow: dict) -> str:
        result = self._json("/prompt", {"prompt": workflow, "client_id": self.client_id})
        if result.get("error") or result.get("node_errors"):
            raise ComfyError(f"ComfyUI rejected workflow: {result}")
        if not isinstance(result.get("prompt_id"), str) or not result["prompt_id"]:
            raise ComfyError("ComfyUI /prompt response has no prompt_id; submission outcome is unknown")
        return result["prompt_id"]

    def wait(self, prompt_id: str, output_node: str | None = None) -> dict:
        deadline = self._clock() + self.timeout
        encoded_id = urllib.parse.quote(prompt_id, safe="")
        while self._clock() < deadline:
            remaining = deadline - self._clock()
            history = self._json(f"/history/{encoded_id}", timeout=max(0.001, remaining))
            entry = history.get(prompt_id)
            if entry:
                status = entry.get("status", {})
                messages = status.get("messages", [])
                errors = [m for m in messages if isinstance(m, (list, tuple)) and m and
                          m[0] in {"execution_error", "execution_interrupted"}]
                if status.get("status_str") == "error" or errors:
                    raise ComfyError(f"ComfyUI execution failed for {prompt_id}: {errors or status}")
                outputs = entry.get("outputs", {})
                selected = outputs.get(str(output_node), {}) if output_node else outputs
                if selected:
                    return entry
                if status.get("completed"):
                    raise ComfyError(f"ComfyUI completed {prompt_id} without the requested image output")
            self._sleep(min(self.poll_interval, max(0, deadline - self._clock())))
        # Never interrupt the shared server: another user/job may own the GPU.
        raise TimeoutError(f"ComfyUI prompt {prompt_id} exceeded {self.timeout:g}s; it may still be queued/running")

    def download_image(self, history_entry: dict, dest: str | Path, output_node: str) -> Path:
        images = history_entry.get("outputs", {}).get(str(output_node), {}).get("images", [])
        if not images:
            raise ComfyError(f"SaveImage node {output_node} produced no images")
        image = images[0]
        query = urllib.parse.urlencode({"filename": image["filename"],
                                        "subfolder": image.get("subfolder", ""),
                                        "type": image.get("type", "output")})
        payload = self._request("/view?" + query)
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        temporary = dest.with_name(dest.name + ".part")
        try:
            temporary.write_bytes(payload)
            with Image.open(temporary) as downloaded:
                downloaded.verify()
            temporary.replace(dest)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return dest


def plan_episode(episode_path: str | Path, characters: dict, config: dict,
                 output_dir: str | Path, *,
                 workflow_template: dict | str | Path | None = None) -> dict:
    """Validate authored data/local guides and build a no-network render plan."""
    episode_path = Path(episode_path).resolve()
    output_dir = Path(output_dir).resolve()
    episode = load_json(episode_path)
    template_info = None
    if workflow_template is not None:
        if isinstance(workflow_template, (str, Path)):
            template_path = Path(workflow_template).resolve()
            template_bytes = template_path.read_bytes()
            workflow_template = load_json(template_path)
            template_source = str(template_path)
        elif isinstance(workflow_template, dict):
            template_bytes = json.dumps(workflow_template, sort_keys=True, ensure_ascii=False).encode("utf-8")
            template_source = "<in-memory>"
        else:
            raise ValueError("workflow_template must be an API JSON object or JSON file path")
        _template_bindings(workflow_template)
        template_info = {"source": template_source, "sha256": hashlib.sha256(template_bytes).hexdigest()}
    cuts = episode.get("cuts")
    if not isinstance(cuts, list) or not cuts:
        raise ValueError("episode must contain a nonempty cuts array")
    seen = set()
    plans = []
    for index, cut in enumerate(cuts, 1):
        if not isinstance(cut, dict):
            raise ValueError("each cut must be an object")
        cut_id = _text(cut.get("id"), "cut.id")
        if cut_id in seen:
            raise ValueError(f"duplicate cut id: {cut_id}")
        seen.add(cut_id)
        stem = f"{index:03d}_" + (re.sub(r"[^\w-]", "_", cut_id)[:60] or "cut")
        graph = build_workflow(cut, characters, config, workflow_template=workflow_template)
        latent = next(node["inputs"] for node in graph.values() if node["class_type"] == "EmptyLatentImage")
        width, height = latent["width"], latent["height"]
        uploads = []
        mapping = {}
        for control in _controls(cut, config):
            local = (episode_path.parent / control["image"]).resolve()
            if not local.is_file():
                raise ValueError(f"cut {cut_id}: guide image not found: {local}")
            with Image.open(local) as guide:
                guide.verify()
            with Image.open(local) as guide:
                guide_width, guide_height = ImageOps.exif_transpose(guide).size
            if guide_width * height != guide_height * width:
                raise ValueError(
                    f"cut {cut_id}: guide aspect ratio {guide_width}x{guide_height} does not match "
                    f"render {width}x{height}: {local}. Prepare a guide with the same aspect ratio; "
                    "ComfyUI otherwise center-crops the pose/background. Same-aspect scaling is allowed."
                )
            digest = hashlib.sha256(local.read_bytes()).hexdigest()[:16]
            name = digest + local.suffix.lower()
            remote = "webtoon_factory/" + name
            mapping[control["image"]] = remote
            uploads.append({"authored_path": control["image"], "local_path": str(local),
                            "upload_name": name, "workflow_image": remote, "status": "upload_required"})
        for node in graph.values():
            if node["class_type"] == "LoadImage":
                node["inputs"]["image"] = mapping[node["inputs"]["image"]]
        graph[output_node_id(graph)]["inputs"]["filename_prefix"] = "webtoon_factory/" + stem
        plans.append({"id": cut_id, "workflow_file": f"workflows/{stem}.json",
                      "image_file": stem + ".png", "expected_size": [width, height],
                      "uploads": uploads, "workflow": graph})
    plan = {"status": "planned_not_rendered", "episode_path": str(episode_path),
            "output_dir": str(output_dir), "cuts": plans}
    if template_info:
        plan["workflow_template"] = template_info
    return plan


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert path.is_file() and path.stat().st_size > 0, f"Missing/empty JSON artifact: {path}"
    assert isinstance(json.loads(path.read_text(encoding="utf-8")), dict), f"Invalid JSON artifact: {path}"


def _portable_path(path: Path, relative_to: Path) -> str:
    """Windows cannot express a relative path between different drives."""
    try:
        return os.path.relpath(path, relative_to)
    except ValueError:
        return str(path)


def _assert_rendered_image(path: Path, expected_size: list[int]) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise ComfyError(f"ComfyUI output file is missing or empty: {path}")
    with Image.open(path) as image:
        if image.format != "PNG" or image.size != tuple(expected_size):
            raise ComfyError(
                f"ComfyUI output must be PNG {expected_size[0]}x{expected_size[1]}; "
                f"received {image.format} {image.width}x{image.height}: {path}"
            )
        image.verify()


def render_episode(episode_path: str | Path, characters: dict, config: dict,
                   output_dir: str | Path, *, dry_run: bool = False,
                   check: bool = False, allow_remote: bool = False, client: ComfyClient | None = None,
                   workflow_template: dict | str | Path | None = None) -> dict:
    """Render cuts and write a relocatable episode.rendered.json on success.

    Dry-run emits workflow JSONs and render_plan.json, with no server requests or
    fake rendered manifest. --check performs GET preflight only and writes nothing.
    Existing final PNGs/manifests are never silently overwritten.
    """
    if dry_run and check:
        raise ValueError("--dry-run and --check are mutually exclusive")
    plan = plan_episode(episode_path, characters, config, output_dir, workflow_template=workflow_template)
    output_dir = Path(output_dir).resolve()
    if not dry_run:
        client = client or ComfyClient(config.get("server", "http://127.0.0.1:8188"),
                                      config.get("timeout", 600), config.get("http_timeout", 30),
                                      config.get("poll_interval", 1), allow_remote=allow_remote)
        checked = client.preflight([item["workflow"] for item in plan["cuts"]])
        if check:
            return checked
    occupied = [output_dir / item["image_file"] for item in plan["cuts"]]
    occupied.append(output_dir / "episode.rendered.json")
    if any(path.exists() for path in occupied):
        raise ValueError("output contains prior rendered files; choose a new --output-dir")
    for item in plan["cuts"]:
        _write_json(output_dir / item["workflow_file"], item["workflow"])
    plan["status"] = "dry_run_not_rendered" if dry_run else "rendering"
    _write_json(output_dir / "render_plan.json", plan)
    if dry_run:
        return plan
    episode = copy.deepcopy(load_json(episode_path))
    cache = {}
    try:
        for cut, item in zip(episode["cuts"], plan["cuts"]):
            graph = copy.deepcopy(item["workflow"])
            replacements = {}
            for upload in item["uploads"]:
                key = upload["workflow_image"]
                if key not in cache:
                    cache[key] = client.upload_image(upload["local_path"], upload["upload_name"])
                replacements[key] = cache[key]
                upload["status"] = "uploaded"
                upload["server_image"] = cache[key]
            for node in graph.values():
                if node["class_type"] == "LoadImage":
                    node["inputs"]["image"] = replacements[node["inputs"]["image"]]
            _write_json(output_dir / item["workflow_file"], graph)
            prompt_id = client.queue(graph)
            item["prompt_id"] = prompt_id
            item["status"] = "queued"
            _write_json(output_dir / "render_plan.json", plan)
            node_id = output_node_id(graph)
            history = client.wait(prompt_id, node_id)
            client.download_image(history, output_dir / item["image_file"], node_id)
            _assert_rendered_image(output_dir / item["image_file"], item["expected_size"])
            cut["image"] = item["image_file"]
            # Retain provenance without rebasing guide paths as local files.
            for field in ("atari", "background"):
                if cut.get(field):
                    cut[field] = _portable_path((Path(episode_path).resolve().parent / cut[field]).resolve(), output_dir)
            for control in cut.get("controls", []):
                control["image"] = _portable_path((Path(episode_path).resolve().parent / control["image"]).resolve(), output_dir)
            item["status"] = "rendered"
            _write_json(output_dir / "render_plan.json", plan)
    except Exception as exc:
        plan["status"] = "failed"
        plan["error"] = str(exc)
        _write_json(output_dir / "render_plan.json", plan)
        raise
    episode["render_status"] = "rendered"
    if "workflow_template" in plan:
        episode["render_workflow_template"] = plan["workflow_template"]
    _write_json(output_dir / "episode.rendered.json", episode)
    plan["status"] = "rendered"
    plan["rendered_manifest"] = str(output_dir / "episode.rendered.json")
    _write_json(output_dir / "render_plan.json", plan)
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("episode", type=Path)
    parser.add_argument("--characters", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--server", help="ComfyUI base URL; overrides config.server")
    parser.add_argument("--allow-remote", action="store_true", help="explicitly allow a non-loopback server")
    parser.add_argument("--workflow", type=Path, help="seven-node API JSON base; config explicitly overrides its defaults")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true", help="write workflows/upload plan without server access")
    modes.add_argument("--check", action="store_true", help="GET preflight only; no upload or queue")
    args = parser.parse_args(argv)
    try:
        config = load_json(args.config)
        if args.server:
            config["server"] = args.server
        result = render_episode(args.episode, load_json(args.characters), config, args.output_dir,
                                dry_run=args.dry_run, check=args.check, allow_remote=args.allow_remote,
                                workflow_template=args.workflow)
        print(json.dumps({key: value for key, value in result.items() if key != "cuts"},
                         ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, ComfyError, TimeoutError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
