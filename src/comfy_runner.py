"""Run one authored ComfyUI API graph unchanged, with a resumable receipt.

This is separate from comfy_client's seven-node SD1.5/SDXL graph adapter.
Inputs/models/custom nodes must already be prepared on the selected server.
No upload, installation, rights clearance, or visual quality review is implied.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
from urllib.parse import urlsplit

from PIL import Image

from .comfy_client import ComfyClient, ComfyError, is_loopback_host, output_node_id


DEFAULT_SERVER = "http://127.0.0.1:8188"
RECEIPT_FILE = "receipt.json"
WORKFLOW_FILE = "workflow_api.json"
OUTPUT_FILE = "image.png"


def _unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _invalid_constant(value: str):
    raise ValueError(f"non-finite JSON number: {value}")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite JSON number: {value}")
    return number


def _read_json(raw: bytes) -> dict:
    value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object,
                       parse_constant=_invalid_constant, parse_float=_finite_float)
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def load_workflow(path: str | Path) -> tuple[bytes, dict, str]:
    """Validate a native API graph without rewriting any authored values."""
    raw = Path(path).read_bytes()
    graph = _read_json(raw)
    if not graph or "nodes" in graph or "links" in graph:
        raise ValueError("expected a native API graph; export API format, not UI nodes/links JSON")
    for node_id, node in graph.items():
        if not isinstance(node_id, str) or not node_id.strip() or not isinstance(node, dict):
            raise ValueError("API graph must be keyed by nonempty node ID strings")
        if set(node) - {"class_type", "inputs", "_meta"}:
            raise ValueError(f"node {node_id!r}: unexpected API node fields")
        kind = node.get("class_type")
        if not isinstance(kind, str) or not kind.strip() or kind != kind.strip():
            raise ValueError(f"node {node_id!r}: class_type must be a nonempty string")
        if not isinstance(node.get("inputs"), dict):
            raise ValueError(f"node {node_id!r}: inputs must be an object")
        if "_meta" in node and not isinstance(node["_meta"], dict):
            raise ValueError(f"node {node_id!r}: _meta must be an object")
        for name, value in node["inputs"].items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"node {node_id!r}: input names must be nonempty strings")
            if isinstance(value, list):
                if (len(value) != 2 or not isinstance(value[0], str) or value[0] not in graph or
                        not isinstance(value[1], int) or isinstance(value[1], bool) or value[1] < 0):
                    raise ValueError(f"node {node_id!r}.{name}: invalid [node ID, output index] link")
    return raw, graph, output_node_id(graph)


def _server_url(value: str, allow_remote: bool) -> str:
    if not isinstance(value, str) or any(ord(char) <= 32 for char in value):
        raise ValueError("server must be an HTTP(S) origin without whitespace")
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or
            parsed.username is not None or parsed.password is not None or
            parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
        raise ValueError("server must be an HTTP(S) origin without credentials, path, query, or fragment")
    # Also reject malformed/out-of-range ports before making a request.
    parsed.port
    if not allow_remote and not is_loopback_host(parsed.hostname):
        raise ValueError("non-loopback server requires explicit --allow-remote")
    return value.rstrip("/")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_receipt(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def _image_info(path: Path) -> dict:
    with Image.open(path) as image:
        if image.format != "PNG":
            raise ValueError("SaveImage result must be PNG")
        width, height = image.size
        image.verify()
    return {"path": OUTPUT_FILE, "sha256": _sha(path.read_bytes()),
            "width": width, "height": height}


def _bound_receipt(output_dir: Path, raw: bytes, node_id: str, server: str,
                   receipt_path: Path | None = None) -> dict:
    receipt = _read_json((receipt_path or output_dir / RECEIPT_FILE).read_bytes())
    expected = {"path": WORKFLOW_FILE, "sha256": _sha(raw)}
    if (receipt.get("schema_version") != 1 or receipt.get("provider") != "comfyui" or
            receipt.get("workflow") != expected or receipt.get("server") != server or
            receipt.get("output_node_id") != node_id):
        raise ValueError("receipt is not bound to this exact workflow, server, and output node")
    if (output_dir / WORKFLOW_FILE).read_bytes() != raw:
        raise ValueError("recorded workflow snapshot differs from the requested workflow")
    return receipt


def validate_completed_output(receipt_path: str | Path,
                              image_path: str | Path) -> tuple[dict, Path]:
    """Verify a completed receipt's exact snapshot and source image bytes.

    Returns (receipt, workflow_snapshot_path). This is integrity/provenance
    evidence only; it does not authorize inputs or approve a finished work.
    """
    receipt_path = Path(receipt_path).resolve()
    directory = receipt_path.parent
    raw, _, node_id = load_workflow(directory / WORKFLOW_FILE)
    receipt_value = _read_json(receipt_path.read_bytes())
    server = _server_url(receipt_value.get("server", ""), allow_remote=True)
    receipt = _bound_receipt(directory, raw, node_id, server, receipt_path)
    prompt_id = receipt.get("prompt_id")
    output = receipt.get("output")
    if (receipt.get("status") != "completed" or not isinstance(prompt_id, str) or
            not prompt_id.strip() or not isinstance(output, dict) or output.get("path") != OUTPUT_FILE):
        raise ValueError("receipt does not record a completed ComfyUI image")
    actual_image = Path(image_path).resolve()
    actual = _image_info(actual_image)
    if any(output.get(key) != value for key, value in actual.items()):
        raise ValueError("image bytes/dimensions differ from the completed receipt")
    return receipt, directory / WORKFLOW_FILE


def run_workflow(workflow_path: str | Path, output_dir: str | Path, *, mode: str = "check",
                 server: str = DEFAULT_SERVER, allow_remote: bool = False,
                 timeout: float = 600, http_timeout: float = 30, poll_interval: float = 1,
                 client: ComfyClient | None = None) -> dict:
    """Check, execute once, or resume an already recorded prompt ID."""
    if mode not in {"check", "execute", "resume"}:
        raise ValueError("mode must be check, execute, or resume")
    server = _server_url(server, allow_remote)
    raw, graph, node_id = load_workflow(workflow_path)
    directory = Path(output_dir).resolve()
    receipt_path = directory / RECEIPT_FILE
    image_path = directory / OUTPUT_FILE
    if mode == "execute" and directory.exists():
        raise ValueError("output directory already exists; preserve it and choose a new --output-dir or --resume")
    if mode == "resume":
        receipt = _bound_receipt(directory, raw, node_id, server)
        if receipt.get("status") == "completed":
            return validate_completed_output(receipt_path, image_path)[0]
        if not isinstance(receipt.get("prompt_id"), str) or not receipt["prompt_id"].strip():
            raise ValueError("submission outcome is unknown or no prompt ID was recorded; do not automatically requeue")
        if image_path.exists():
            raise ValueError("unrecorded output already exists; preserve it for manual recovery, do not requeue")
    client = client or ComfyClient(server, timeout, http_timeout, poll_interval, allow_remote=allow_remote)
    if client.base != server:
        raise ValueError("client server differs from the requested server")
    if mode != "resume":
        client._json("/system_stats")
        preflight = client.preflight(graph)
        if mode == "check":
            return {**preflight, "status": "checked_not_queued", "server": server,
                    "workflow_sha256": _sha(raw), "output_node_id": node_id,
                    "rights_review": "not_issued", "quality_review": "not_reviewed"}
        directory.mkdir(parents=True, exist_ok=False)
        (directory / WORKFLOW_FILE).write_bytes(raw)
        receipt = {"schema_version": 1, "provider": "comfyui", "status": "prepared",
                   "server": server, "prompt_id": None,
                   "workflow": {"path": WORKFLOW_FILE, "sha256": _sha(raw)},
                   "output_node_id": node_id, "created_at": _now(),
                   "rights_review": "not_issued", "quality_review": "not_reviewed"}
        _write_receipt(receipt_path, receipt)
        # Persist ambiguity BEFORE POST. A crash/lost response must never invite
        # a duplicate submission. Only an acknowledged ID enables --resume.
        receipt.update(status="submission_unknown", submission_started_at=_now(),
                       next_action="do_not_requeue_automatically")
        _write_receipt(receipt_path, receipt)
        try:
            receipt["prompt_id"] = client.queue(graph)
        except Exception as exc:
            receipt["last_error"] = str(exc)
            _write_receipt(receipt_path, receipt)
            raise
        receipt.update(status="submitted", next_action="resume_only_do_not_requeue")
        _write_receipt(receipt_path, receipt)
    try:
        history = client.wait(receipt["prompt_id"], node_id)
        if history.get("status", {}).get("completed") is not True:
            raise ComfyError("server output is not confirmed completed; resume this prompt later")
        images = history.get("outputs", {}).get(node_id, {}).get("images", [])
        if (not isinstance(images, list) or len(images) != 1 or
                not isinstance(images[0], dict) or not isinstance(images[0].get("filename"), str) or
                not images[0]["filename"]):
            raise ComfyError("one-cut execution requires exactly one image from the SaveImage node")
        # Recheck immediately before download; never overwrite a prior final.
        if image_path.exists():
            raise ValueError("output image already exists; preserve it for manual recovery")
        client.download_image(history, image_path, node_id)
        output = _image_info(image_path)
        receipt.update(status="completed", output=output, completed_at=_now(),
                       server_output=images[0], next_action="review_output")
        receipt.pop("last_error", None)
        _write_receipt(receipt_path, receipt)
        return receipt
    except Exception as exc:
        receipt["last_error"] = str(exc)
        _write_receipt(receipt_path, receipt)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("workflow", type=Path, help="native exported API JSON, not UI nodes/links JSON")
    parser.add_argument("--output-dir", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true", help="GET preflight only; no files or queue writes")
    modes.add_argument("--execute", action="store_true", help="explicitly submit one authored graph once")
    modes.add_argument("--resume", action="store_true", help="wait/download using receipt.json; never POST again")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--allow-remote", action="store_true", help="explicitly allow a non-loopback server")
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--http-timeout", type=float, default=30)
    parser.add_argument("--poll-interval", type=float, default=1)
    args = parser.parse_args(argv)
    mode = "execute" if args.execute else "resume" if args.resume else "check"
    try:
        result = run_workflow(args.workflow, args.output_dir, mode=mode, server=args.server,
                              allow_remote=args.allow_remote, timeout=args.timeout,
                              http_timeout=args.http_timeout, poll_interval=args.poll_interval)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except Exception as exc:
        print(f"ComfyUI runner: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
