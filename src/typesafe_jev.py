"""Small, explicit TypeSafe HTTP adapter; no network activity at import time.

Images are an experimental TypeSafe feature. These judgments compare supplied
material only and do not establish copyright clearance or search the internet.
"""
from __future__ import annotations

import base64
import binascii
from http.client import HTTPException
import io
import json
import math
import os
from pathlib import Path
import re
from urllib import error, request

from PIL import Image, ImageOps


DEFAULT_MODEL = "jev-1.13.0"
API_BASE = "https://api.typesafe.ai"
LOCAL_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
MAX_BODY_BYTES = 32 * 1024 * 1024
MAX_IMAGE_BYTES = 16 * 1024 * 1024


def image_asset(path, box=None):
    """Prepare a file or Pillow image, optionally cropped, without mutating it."""
    try:
        source = path.copy() if isinstance(path, Image.Image) else Image.open(Path(path))
        with source as original:
            if getattr(original, "n_frames", 1) != 1:
                raise ValueError("Animated images are not supported")
            original.load()
            image = ImageOps.exif_transpose(original).convert("RGBA")
            if box is not None:
                if (not isinstance(box, (tuple, list)) or len(box) != 4
                        or any(not isinstance(edge, int) or isinstance(edge, bool) for edge in box)
                        or not 0 <= box[0] < box[2] <= image.width
                        or not 0 <= box[1] < box[3] <= image.height):
                    raise ValueError("Invalid image crop bounds")
                image = image.crop(box)
            image.thumbnail((1568, 1568), Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (max(280, image.width), max(280, image.height)), "white")
            canvas.paste(image, ((canvas.width - image.width) // 2,
                                 (canvas.height - image.height) // 2), image)
            buffer = io.BytesIO()
            canvas.save(buffer, format="PNG")
            data = buffer.getvalue()
    except (OSError, ValueError, Image.DecompressionBombError):
        raise ValueError("TypeSafe image cannot be prepared as a still PNG") from None
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("TypeSafe prepared image exceeds 16 MiB")
    return {"type": "image", "format": "png", "data_base64": base64.b64encode(data).decode("ascii")}


def _probability(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and 0 <= value <= 1 and math.isfinite(value))


def validate_choice(answer, options):
    """Validate a complete Choice answer against the options actually sent."""
    try:
        options = list(options)
    except TypeError:
        raise ValueError("TypeSafe Choice needs named options") from None
    if (len(options) < 2 or any(not isinstance(key, str) or not key.strip() for key in options)
            or len(set(options)) != len(options)):
        raise ValueError("TypeSafe Choice needs at least two unique option names")
    if (not isinstance(answer, dict)
            or set(answer) != {"type", "choice", "confidence", "probabilities"}
            or answer.get("type") != "choice" or answer.get("choice") not in options
            or not _probability(answer.get("confidence"))):
        raise ValueError("TypeSafe returned an invalid Choice answer")
    probabilities = answer.get("probabilities")
    if (not isinstance(probabilities, dict) or set(probabilities) != set(options)
            or any(not _probability(value) for value in probabilities.values())
            or abs(sum(probabilities.values()) - 1.0) > 0.02
            or probabilities[answer["choice"]] < max(probabilities.values())):
        raise ValueError("TypeSafe returned invalid Choice probabilities")
    return answer


def _model_name(model):
    if not isinstance(model, str) or re.fullmatch(r"jev-[0-9]+\.[0-9]+\.[0-9]+", model) is None:
        raise ValueError("TypeSafe requires a pinned Jev model version")


def _question_types(questions):
    if not isinstance(questions, dict) or not questions:
        raise ValueError("TypeSafe questions must be a nonempty object")
    for name, question in questions.items():
        if (not isinstance(name, str) or not name.strip() or not isinstance(question, dict)
                or question.get("type") not in ("choice", "noul")
                or not isinstance(question.get("instructions"), (str, dict, list))):
            raise ValueError("TypeSafe supports explicit Choice and Noul questions")
        if question["type"] == "choice":
            criteria = question.get("criteria")
            if (not isinstance(criteria, dict) or len(criteria) < 2
                    or any(not isinstance(key, str) or not key.strip() for key in criteria)):
                raise ValueError("TypeSafe Choice requires at least two named criteria")


def _validate_assets(assets):
    if not isinstance(assets, dict):
        raise ValueError("TypeSafe assets must be an object")
    decoded_bytes = 0
    for reference, asset in assets.items():
        if (not isinstance(reference, str) or not reference.strip()
                or len(reference.encode("utf-8")) > 1024 or not isinstance(asset, dict)
                or set(asset) != {"type", "format", "data_base64"}
                or asset.get("type") != "image" or asset.get("format") not in ("png", "jpg", "jpeg")
                or not isinstance(asset.get("data_base64"), str)):
            raise ValueError("TypeSafe image asset is invalid")
        try:
            data = base64.b64decode(asset["data_base64"], validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("TypeSafe image asset has invalid base64") from None
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError("TypeSafe image asset exceeds 16 MiB")
        decoded_bytes += len(data)
    if decoded_bytes > MAX_BODY_BYTES or sum(len(key.encode("utf-8")) for key in assets) > 65536:
        raise ValueError("TypeSafe image assets exceed request limits")


def _local_api_key():
    """Read this project's one credential without exporting dotenv variables."""
    try:
        text = LOCAL_ENV_FILE.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return ""
    except (OSError, UnicodeError):
        raise ValueError("TypeSafe local credential file cannot be read") from None
    key = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if name.strip() != "TYPESAFE_API_KEY":
            if re.match(r"TYPESAFE_API_KEY(?:\s|$)", line):
                raise ValueError("TypeSafe local credential assignment is invalid")
            continue
        if not separator:
            raise ValueError("TypeSafe local credential assignment is invalid")
        if key is not None:
            raise ValueError("TypeSafe local credential assignment is duplicated")
        value = value.strip()
        if value.startswith(("'", '"')):
            end = value.find(value[0], 1)
            if end < 0 or (value[end + 1:].strip() and not value[end + 1:].lstrip().startswith("#")):
                raise ValueError("TypeSafe local credential assignment is invalid")
            value = value[1:end]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0]
        key = value.strip()
    return key or ""


def _api_key():
    key = _local_api_key() or (os.environ.get("TYPESAFE_API_KEY") or "").strip()
    if not key:
        key = (os.environ.get("TYPESAFE_API_TOKEN") or "").strip()
    if not key or any(ord(character) < 33 or ord(character) > 126 for character in key):
        raise ValueError("TypeSafe API credential is missing or invalid")
    return key


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _reject_constant(value):
    raise ValueError("Non-finite JSON number")


def _http(method, path, payload=None, *, timeout=90, images=False):
    try:
        valid_timeout = (isinstance(timeout, (int, float)) and not isinstance(timeout, bool)
                         and timeout > 0 and math.isfinite(timeout))
    except OverflowError:
        valid_timeout = False
    if not valid_timeout:
        raise ValueError("TypeSafe timeout must be a finite positive number")
    data = None
    if payload is not None:
        try:
            data = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                              separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError, UnicodeError, RecursionError):
            raise ValueError("TypeSafe request is not valid finite UTF-8 JSON") from None
        if len(data) > MAX_BODY_BYTES:
            raise ValueError("TypeSafe request body exceeds 32 MiB")
    headers = {"Authorization": "Bearer " + _api_key(), "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if images:
        headers["TypeSafe-Danger-Zone-Images"] = "true"
    http_request = request.Request(API_BASE + path, data=data, headers=headers, method=method)
    try:
        with request.build_opener(_NoRedirect).open(http_request, timeout=timeout) as response:
            status = response.status
            body = response.read(MAX_BODY_BYTES + 1)
    except error.HTTPError as failure:
        status = failure.code
        failure.close()
        raise ValueError(f"TypeSafe service returned HTTP {status}") from None
    except (error.URLError, OSError, TimeoutError, HTTPException):
        raise ValueError("TypeSafe service connection failed or timed out") from None
    if status != 200:
        raise ValueError(f"TypeSafe service returned HTTP {status}")
    if len(body) > MAX_BODY_BYTES:
        raise ValueError("TypeSafe service response exceeds 32 MiB")
    try:
        result = json.loads(body.decode("utf-8"), parse_constant=_reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("TypeSafe service returned invalid JSON") from None
    if not isinstance(result, dict):
        raise ValueError("TypeSafe service returned an invalid response object")
    return result


def list_models(*, timeout=90):
    """Explicitly query the authenticated account; never expose credentials."""
    response = _http("GET", "/v1/models", timeout=timeout)
    models = response.get("models")
    if (not isinstance(models, list) or any(
            not isinstance(model, dict) or any(not isinstance(model.get(key), str) or not model[key].strip()
                                              for key in ("name", "description", "release_date"))
            for model in models)):
        raise ValueError("TypeSafe service returned an invalid model list")
    return response


def ask(state, questions, assets=None, *, model=DEFAULT_MODEL, timeout=90):
    """Explicitly submit one request and validate all answers; never retry."""
    _model_name(model)
    if not isinstance(state, (str, dict, list)):
        raise ValueError("TypeSafe state must be text, an object, or an array")
    _question_types(questions)
    assets = {} if assets is None else assets
    _validate_assets(assets)
    payload = {"model": model, "state": state, "questions": questions}
    if assets:
        payload["assets"] = assets
    response = _http("POST", "/v1/systemone", payload, timeout=timeout, images=bool(assets))
    answers = response.get("answers")
    if (response.get("model") != model or not isinstance(answers, dict)
            or set(answers) != set(questions)):
        raise ValueError("TypeSafe response model or question names do not match the request")
    for name, question in questions.items():
        answer = answers[name]
        if question["type"] == "choice":
            validate_choice(answer, question["criteria"])
        elif (not isinstance(answer, dict) or set(answer) != {"type", "noul"}
              or answer.get("type") != "noul" or not _probability(answer.get("noul"))):
            raise ValueError("TypeSafe returned an invalid Noul answer")
    if "usage" in response:
        usage = response["usage"]
        if (not isinstance(usage, dict) or any(
                key in usage and (not isinstance(usage[key], int) or isinstance(usage[key], bool) or usage[key] < 0)
                for key in ("input_tokens", "output_tokens"))):
            raise ValueError("TypeSafe returned invalid token usage")
    return response
