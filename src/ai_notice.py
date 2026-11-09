"""Local typography and notice-first review packages; never grant release approval."""
from __future__ import annotations

import hashlib
import html
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit
import zipfile

from PIL import Image, ImageDraw, ImageFont

from .webtoon_stitcher import _smart_slices
from .font_policy import resolve_font, font_record, source_font_records, write_font_notices

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NOTICE = ROOT / "workspace/production/ai_notice/v4/notice.json"
if not DEFAULT_NOTICE.is_file():
    DEFAULT_NOTICE = ROOT / "docs/public/templates/notice.example.json"


def _owned(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Keep notice inputs and outputs in this project")
    return path


def _sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _wrap(text, font, width):
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            candidate = line + " " + word if line else word
            if line and font.getlength(candidate) > width:
                lines.append(line)
                line = ""
            if font.getlength(word) > width:
                for character in word:
                    if line and font.getlength(line + character) > width:
                        lines.append(line)
                        line = ""
                    line += character
            else:
                line = line + " " + word if line else word
        if line:
            lines.append(line)
    return lines


def notice_image(config_path=DEFAULT_NOTICE, report_channel=None):
    config_path = _owned(config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    channel = report_channel if report_channel is not None else config.get("report_channel")
    if channel:
        parsed = urlsplit(channel)
        if (len(channel) > 240 or any(ord(c) < 32 for c in channel)
                or parsed.scheme not in ("mailto", "https")
                or parsed.username or parsed.password
                or (parsed.scheme == "https" and not parsed.hostname)
                or (parsed.scheme == "mailto" and ("@" not in parsed.path or parsed.query))):
            raise ValueError("Reporting channel must be an actual mailto or HTTPS address")
    width = config["width"]
    if width != 800:
        raise ValueError("This notice template is authored at 800px")
    regular_path = resolve_font(_owned(ROOT / config["font"]))
    bold_path = resolve_font(_owned(ROOT / config["font_bold"]))
    regular = ImageFont.truetype(str(regular_path), config["font_size"])
    bold = ImageFont.truetype(str(bold_path), config["title_size"])
    rows, rules = [], []
    compact = config.get("layout") == "formal_compact"
    margin, y = (56, 42) if compact else (48, 54)
    for line in _wrap(config["title"], bold, width - 2 * margin):
        rows.append((line, margin, y, bold, "#20252a"))
        y += 50 if compact else 52
    if compact:
        rules.append((y + 7, "#5d666e"))
        y += 34
    else:
        y += 30
    for paragraph in config["paragraphs"]:
        for line in _wrap(paragraph, regular, width - 2 * margin):
            rows.append((line, margin, y, regular, "#30363b"))
            y += 42 if compact else 43
        y += 18 if compact else 21
    if compact:
        y += 2
        rules.append((y, "#d0d4d7"))
        y += 25
        small = ImageFont.truetype(str(regular_path), 24)
        footer = config.get("report_sentence") or "권리 관련 제보: " + (channel or config["report_channel_label"])
        for paragraph in [footer, config["responsibility_note"]]:
            for line in _wrap(paragraph, small, width - 2 * margin):
                rows.append((line, margin, y, small, "#626b73"))
                y += 34
            y += 8
        if not channel:
            tiny = ImageFont.truetype(str(regular_path), 21)
            rows.append((config["draft_label"], margin, y + 2, tiny, "#626b73"))
            y += 32
    else:
        contact = ("권리 관련 제보: " + channel if channel else
                   "제보 예정 창구: " + config.get("report_channel_label", "접수처 미정")
                   + "\n내부 검토용 · 접수처 개설 전 · 공개 보류")
        for line in _wrap(contact, regular, width - 2 * margin):
            rows.append((line, margin, y, regular, "#444444" if channel else "#8a3030"))
            y += 43
    image = Image.new("RGB", (width, y + (38 if compact else 56)), "white")
    draw = ImageDraw.Draw(image)
    for rule_y, color in rules:
        draw.line((margin, rule_y, width - margin, rule_y), fill=color, width=1)
    boxes = []
    for text, x, top, font, color in rows:
        draw.text((x, top), text, font=font, fill=color, anchor="lt")
        box = draw.textbbox((x, top), text, font=font, anchor="lt")
        if not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= image.height):
            raise ValueError("Notice text exceeds its canvas")
        boxes.append(list(box))
    if not compact:
        draw.line((48, image.height - 16, width - 48, image.height - 16), fill="#b5b5b5", width=1)
    qa = {}
    if config.get("notice_qa_report"):
        qa_path = _owned(ROOT / config["notice_qa_report"])
        qa = {"path": str(qa_path.relative_to(ROOT)), "sha256": _sha(qa_path),
              "status": "not_cleared_requires_separate_review"}
    return image, {"version": config["version"], "config_sha256": _sha(config_path),
                   "renderer_sha256": _sha(Path(__file__)),
                   "font_sha256": _sha(regular_path), "bold_font_sha256": _sha(bold_path),
                   "fonts_used": [font_record(regular_path), font_record(bold_path)],
                   "report_channel": channel, "report_channel_verified": False,
                   "report_channel_configured": bool(channel), "text_boxes": boxes,
                   "notice_legal_qa": qa,
                   "provider": "local_typography", "new_imagegen_calls": 0,
                   "legal_clearance": "not_issued", "publication_approved": False}


def package_review(source_manifest, output_dir, *, notice=DEFAULT_NOTICE, report_channel=None):
    """Prepend a mandatory notice to unchanged pixels in a new review directory."""
    source_manifest, output = _owned(source_manifest), _owned(output_dir)
    if output.exists():
        raise FileExistsError("Choose a new output directory; preserve existing candidates")
    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    source_fonts = source_font_records(source_manifest.parent, source)
    if source.get("generator") == "webtoon-notice-review-package" or any(c["id"] == "ai_notice" for c in source["cuts"]):
        raise ValueError("This source already has an AI notice")
    master = _owned(source_manifest.parent / source["full"]["path"])
    source_hash, manifest_hash = _sha(master), _sha(source_manifest)
    if source_hash != source["full"]["sha256"]:
        raise ValueError("Source master differs from its manifest")
    with Image.open(master) as opened:
        body = opened.convert("RGB")
    if body.size != (source["width"], source["height"]) or body.width != 800:
        raise ValueError("Source dimensions differ or are not 800px wide")
    header, notice_record = notice_image(notice, report_channel)
    if body.width * (body.height + header.height) > 100_000_000:
        raise ValueError("Review package exceeds pixel budget")
    offset = header.height
    cuts = [{"id": "ai_notice", "x": 0, "y": 0, "width": 800, "height": offset, "gap_after": 0}]
    cuts.extend({**cut, "y": cut["y"] + offset} for cut in source["cuts"])
    full = Image.new("RGB", (800, offset + body.height), "white")
    full.paste(header, (0, 0))
    full.paste(body, (0, offset))
    if full.crop((0, offset, 800, full.height)).tobytes() != body.tobytes():
        raise ValueError("Body pixels changed while prepending notice")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="notice-review-", dir=output.parent) as temporary:
        stage = Path(temporary) / "result"
        stage.mkdir()
        full.save(stage / "full_strip.png")
        header.save(stage / "ai_notice.png")
        header.resize((390, round(header.height * 390 / 800)), Image.Resampling.LANCZOS).save(stage / "ai_notice_390.png")
        parts = []
        for number, (start, end) in enumerate(_smart_slices(full.height, cuts, 4000), 1):
            path = stage / f"slice_{number:03d}.png"
            full.crop((0, start, 800, end)).save(path)
            parts.append({"path": path.name, "y": start, "height": end - start, "sha256": _sha(path)})
        y = 0
        for part in parts:
            with Image.open(stage / part["path"]) as opened:
                pixels = opened.convert("RGB")
                if part["y"] != y or pixels.tobytes() != full.crop((0, y, 800, y + part["height"])).tobytes():
                    raise ValueError("Split pixels or order changed")
            y += part["height"]
        if y != full.height:
            raise ValueError("Incomplete split coverage")
        blockers = ["underlying_work_rights_and_required_qa_not_cleared", "new_composite_visual_review_pending"]
        blockers.append("notice_legal_qa_not_cleared")
        if not notice_record["report_channel_configured"]:
            blockers.append("actual_report_channel_not_supplied")
        else:
            blockers.append("actual_report_channel_not_verified")
        fonts = write_font_notices(stage, source_fonts + notice_record['fonts_used'])
        manifest = {"generator": "webtoon-notice-review-package", "schema_version": 1,
                    "font_policy": "open-fonts-v1", "fonts_used": fonts,
                    "source_font_provenance": source.get('source_font_provenance', 'verified') if source.get('font_policy') == 'open-fonts-v1' else 'legacy_unverified',
                    "font_licenses_sha256": _sha(stage / 'font_licenses.json'),
                    "title": source.get("title", "Webtoon review"), "width": 800, "height": full.height,
                    "full": {"path": "full_strip.png", "sha256": _sha(stage / "full_strip.png")},
                    "parts": parts, "cuts": cuts, "notice": notice_record,
                    "notice_image_sha256": _sha(stage / "ai_notice.png"),
                    "source_manifest": str(source_manifest.relative_to(ROOT)), "source_manifest_sha256": manifest_hash,
                    "source_master_sha256": source_hash, "body_offset_y": offset, "body_pixels_unchanged": True,
                    "status": "internal_review_candidate", "release_approved": False, "blockers": blockers,
                    "new_model_calls": 0, "work_qa_status": "not_transferred_from_source"}
        _save(stage / "manifest.json", manifest)
        tags = "".join(f'<img src="{p["path"]}" width="800" height="{p["height"]}" alt="검토 원고 {i}">' for i, p in enumerate(parts, 1))
        (stage / "read.html").write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(manifest["title"]) + ' · 고지 포함 검토본</title><style>body{margin:0;background:white}main{max-width:800px;margin:auto}img{display:block;width:100%;height:auto}</style><main>' + tags + '</main></html>', encoding="utf-8")
        with zipfile.ZipFile(stage / "review_images.zip", "w", zipfile.ZIP_STORED) as archive:
            archive.write(stage / 'font_licenses.json', 'font_licenses.json')
            for license_file in sorted((stage / 'licenses').glob('*.txt')):
                archive.write(license_file, 'licenses/' + license_file.name)
            for part in parts:
                archive.write(stage / part["path"], part["path"])
        with zipfile.ZipFile(stage / "review_images.zip") as archive:
            if archive.testzip() is not None:
                raise ValueError("Invalid review ZIP")
        if _sha(master) != source_hash or _sha(source_manifest) != manifest_hash:
            raise ValueError("Source changed during packaging")
        if not stage.resolve().is_relative_to(ROOT):
            raise ValueError("Unexpected staging path")
        os.replace(stage, output)
    return {"output": str(output), "size": list(full.size), "body_pixels_unchanged": True,
            "status": "internal_review_candidate", "release_approved": False, "blockers": blockers}
