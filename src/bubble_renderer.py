"""Pixel-measured Korean lettering without cropping the source artwork.

Balloon geometry adapted from ahmet360/manga-studio ``bubbles.py`` (MIT).
Copyright (c) 2026 ahmet360. See THIRD_PARTY_NOTICES.md and vendor/manga-studio/LICENSE.
Source: https://github.com/ahmet360/manga-studio/blob/main/bubbles.py

``box`` is [left, top, width, height], normalized to the image; it includes
the balloon body (and reserves room for a default tail). ``tail`` is an
optional normalized endpoint. Explicit tail endpoints must stay on canvas.
Rendering returns a copy, preserves canvas dimensions, and raises instead
of dropping dialogue or accepting overlapping balloons. Automatic placement
is a deterministic row-major layout; it does not identify faces in artwork.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import unicodedata

from PIL import Image, ImageDraw, ImageFont
from .font_policy import resolve_font, entry_font


class BubbleLayoutError(ValueError):
    """Dialogue cannot be rendered safely at the requested size/position."""


_KINDS = {"normal", "shout", "thought", "narration", "sfx"}
_POSITIONS = {"auto", "top-left", "top-right", "bottom-left", "bottom-right",
              "top", "bottom", "center"}
_CJK = re.compile(r"[\u1100-\u11ff\u2e80-\ua4cf\uac00-\ud7af\uf900-\ufaff]")


def _font_candidates(font_path):
    try:
        return [str(resolve_font(font_path))]
    except ValueError as error:
        raise BubbleLayoutError(str(error)) from error


def _load_font(font_path, size: int, text: str):
    candidates = _font_candidates(font_path)
    unsupported = []
    for candidate in candidates:
        try:
            font = ImageFont.truetype(candidate, size=size)
        except (OSError, ValueError):
            continue
        # FreeType renders missing characters with the .notdef glyph. A font
        # that loads successfully can still be unable to print Korean.
        missing = font.getmask("\U0010ffff")
        missing_key = (missing.size, bytes(missing))
        for char in set(_CJK.findall(text)):
            mask = font.getmask(char)
            if (mask.size, bytes(mask)) == missing_key:
                unsupported.append(candidate)
                break
        else:
            return font
    extra = " Loaded fonts lack required Korean/CJK glyphs." if unsupported else ""
    raise BubbleLayoutError(
        "No usable font found. Set WEBTOON_FONT or --font to a Korean-capable "
        "approved open font (verified Pretendard Medium/Bold)." + extra
    )


def _units(text: str):
    """Keep combining marks with their base without an extra dependency."""
    units = []
    for char in text:
        if units and (unicodedata.combining(char) or char in "\ufe0e\ufe0f\u200d"
                      or units[-1].endswith("\u200d")):
            units[-1] += char
        else:
            units.append(char)
    return units


def _width(font, text: str) -> float:
    box = font.getbbox(text)
    return max(float(font.getlength(text)), float(box[2] - box[0]))


def wrap_text(text: str, font, max_width: int) -> list[str]:
    """Wrap by measured pixels, including space-free Hangul and newlines."""
    if max_width <= 0:
        raise BubbleLayoutError("Text box has no usable horizontal space.")
    lines = []
    for paragraph in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        current = ""
        for unit in _units(paragraph):
            if _width(font, unit) > max_width:
                raise BubbleLayoutError("A single glyph is wider than the text box.")
            if current and _width(font, current + unit) > max_width:
                # Prefer a space boundary for Latin/Korean mixed sentences;
                # otherwise split the Hangul run at a character boundary.
                split_at = current.rfind(" ")
                if (split_at > 0 and current[split_at + 1:]
                        and _width(font, current[split_at + 1:] + unit) <= max_width):
                    lines.append(current[:split_at].rstrip())
                    current = current[split_at + 1:] + unit
                else:
                    lines.append(current.rstrip())
                    current = unit.lstrip()
            else:
                current += unit
        lines.append(current.rstrip())
    return lines


def _text_metrics(font, lines):
    ascent, descent = font.getmetrics()
    line_height = max(1, math.ceil((ascent + descent) * 1.08))
    return max((_width(font, line) for line in lines), default=0), line_height * len(lines), line_height


def _factors(kind):
    # A centered rectangle with both dimensions <= .64 of an ellipse is
    # entirely inside its edge. Shout uses a smaller notch-safe rectangle.
    return {"normal": .64, "thought": .60, "shout": .50,
            "narration": 1., "sfx": 1.}[kind]


def _content_box(box, kind, padding):
    x0, y0, x1, y1 = box
    factor = _factors(kind)
    width = max(0, math.floor((x1 - x0 - 2 * padding) * factor))
    height = max(0, math.floor((y1 - y0 - 2 * padding) * factor))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return (cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2)


def _overlaps(a, b, gap=6):
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0]
                or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def _normalized(values, count, label):
    if not isinstance(values, (list, tuple)) or len(values) != count:
        raise BubbleLayoutError(f"{label} must contain {count} normalized numbers.")
    if any(isinstance(v, bool) or not isinstance(v, (int, float))
           or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
        raise BubbleLayoutError(f"{label} values must be finite numbers between 0 and 1.")
    return values


def _explicit_box(values, width, height):
    x, y, w, h = _normalized(values, 4, "box")
    if w <= 0 or h <= 0 or x + w > 1.00000001 or y + h > 1.00000001:
        raise BubbleLayoutError("box must have positive dimensions and stay inside the image.")
    return (round(x * width), round(y * height), round((x + w) * width), round((y + h) * height))


def _body(allocation, kind):
    x0, y0, x1, y1 = allocation
    if kind in {"normal", "thought"}:
        y1 -= max(8, round((y1 - y0) * .16))
    return (x0, y0, x1, y1)


def _anchor(position, w, h, width, height, margin):
    left, right = margin, width - margin - w
    top, bottom = margin, height - margin - h
    center_x, center_y = (width - w) // 2, (height - h) // 2
    return {"top-left": (left, top), "top-right": (right, top),
            "bottom-left": (left, bottom), "bottom-right": (right, bottom),
            "top": (center_x, top), "bottom": (center_x, bottom),
            "center": (center_x, center_y)}[position]


def _place(position, w, h, width, height, margin, occupied):
    if position != "auto":
        x, y = _anchor(position, w, h, width, height, margin)
        return (x, y, x + w, y + h)
    # Candidate shelves start after each previously reserved footprint.
    ys = sorted({margin, *(math.ceil(b[3]) + 10 for b in occupied)})
    xs = sorted({margin, *(math.ceil(b[2]) + 10 for b in occupied)})
    for y in ys:
        for x in xs:
            candidate = (x, y, x + w, y + h)
            if candidate[2] <= width - margin and candidate[3] <= height - margin:
                if not any(_overlaps(candidate, other) for other in occupied):
                    return candidate
    return None


def _tail_points(body, allocation, target, kind):
    if kind not in {"normal", "thought"}:
        return []
    x0, y0, x1, y1 = body
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
    tip = target or (x0 + (x1 - x0) * .68, allocation[3] - 1)
    dx, dy = tip[0] - cx, tip[1] - cy
    if not dx and not dy:
        return []
    radius = math.sqrt((dx / max(rx, 1)) ** 2 + (dy / max(ry, 1)) ** 2)
    if radius <= 1:
        return []
    bx, by = cx + dx / radius * .84, cy + dy / radius * .84
    length = math.hypot(dx, dy)
    half = max(4, min(rx, ry) * .12)
    px, py = -dy / length * half, dx / length * half
    return [(bx + px, by + py), tip, (bx - px, by - py)]


def _footprint(allocation, tail):
    xs = [allocation[0], allocation[2], *(p[0] for p in tail)]
    ys = [allocation[1], allocation[3], *(p[1] for p in tail)]
    return (min(xs), min(ys), max(xs), max(ys))


def _thought_dots(body, tail):
    if not tail:
        return []
    origin = ((tail[0][0] + tail[2][0]) / 2, (tail[0][1] + tail[2][1]) / 2)
    half_size = min(body[2] - body[0], body[3] - body[1]) / 2
    dots = []
    for ratio, radius in ((.45, 5), (.7, 4), (.92, 3)):
        x = origin[0] + (tail[1][0] - origin[0]) * ratio
        y = origin[1] + (tail[1][1] - origin[1]) * ratio
        dots.append((x, y, min(radius, max(1, half_size * .05))))
    return dots


def _draw_shape(draw, body, kind, tail, outline):
    x0, y0, x1, y1 = body
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
    if kind == "sfx":
        return
    if kind == "thought" and tail:
        for x, y, radius in _thought_dots(body, tail):
            draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                         fill="white", outline="black", width=outline)
    elif tail:
        draw.polygon(tail, fill="white", outline="black", width=outline)
    if kind == "narration":
        draw.rectangle(body, fill="white", outline="black", width=outline)
    elif kind == "shout":
        # Outer tips fit the reserved box; inward notches retain a safe core.
        points = []
        for i in range(44):
            angle = 2 * math.pi * i / 44
            radius = 1. if i % 2 == 0 else .78
            points.append((cx + math.cos(angle) * rx * radius,
                           cy + math.sin(angle) * ry * radius))
        draw.polygon(points, fill="white", outline="black", width=outline)
    elif kind == "thought":
        # The reference comics use a quiet oval with detached thought dots.
        # Keep the measured body; ornate scallops distract from small faces.
        draw.ellipse(body, fill="white", outline="black", width=outline)
    else:
        draw.ellipse(body, fill="white", outline="black", width=outline)


def render_bubbles(image: Image.Image, dialogue: list[dict], *, font_path=None,
                   font_size: int = 30, min_font_size: int = 16) -> Image.Image:
    """Composite all dialogue or raise :class:`BubbleLayoutError`.

    Entries accept ``speaker`` (metadata), ``text``, ``type``, ``position``,
    optional normalized ``box`` and optional normalized ``tail`` endpoint.
    ``font_size`` is in output pixels and only shrinks when necessary, down
    to ``min_font_size``. There is no clipping, ellipsis or dropped dialogue.
    RGB input returns RGB; alpha-bearing input returns RGBA with its alpha.
    """
    if not isinstance(image, Image.Image) or image.width < 1 or image.height < 1:
        raise ValueError("image must be a nonempty PIL Image.")
    if not isinstance(dialogue, list):
        raise ValueError("dialogue must be a list of objects.")
    if (isinstance(font_size, bool) or isinstance(min_font_size, bool)
            or not isinstance(font_size, int) or not isinstance(min_font_size, int)
            or not 1 <= min_font_size <= font_size <= 512):
        raise ValueError("Require integer 1 <= min_font_size <= font_size <= 512.")
    if any(isinstance(entry,dict) and entry.get('style')=='editorial' for entry in dialogue):
        from .editorial_lettering import render_editorial
        return render_editorial(image,dialogue,font_path=font_path,font_size=font_size,min_font_size=min_font_size)
    output_mode = "RGBA" if image.mode in {"RGBA", "LA", "PA"} or "transparency" in image.info else "RGB"
    result = image.convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = image.size
    margin = max(4, min(18, width // 40, height // 40))
    occupied = []
    for index, entry in enumerate(dialogue):
        try:
            if not isinstance(entry, dict):
                raise BubbleLayoutError("Each dialogue entry must be an object.")
            text = entry.get("text")
            if not isinstance(text, str) or not text.strip():
                raise BubbleLayoutError("text must be a nonempty string.")
            if any(unicodedata.category(c) == "Cc" and c not in "\n\r" for c in text):
                raise BubbleLayoutError("text contains unsupported control characters (replace tabs with spaces).")
            kind, position = entry.get("type", "normal"), entry.get("position", "auto")
            if kind not in _KINDS or position not in _POSITIONS:
                raise BubbleLayoutError(f"Unsupported type {kind!r} or position {position!r}.")
            target = None
            if "tail" in entry:
                tx, ty = _normalized(entry["tail"], 2, "tail")
                target = (tx * (width - 1), ty * (height - 1))
            explicit = _explicit_box(entry["box"], width, height) if "box" in entry else None
            fitted = None
            entry_font_size = entry.get("font_size", font_size)
            if type(entry_font_size) is not int or entry_font_size < min_font_size:
                raise BubbleLayoutError("font_size must be an integer at least min_font_size.")
            for size in range(entry_font_size, min_font_size - 1, -1):
                font = _load_font(entry_font(entry, font_path), size, text)
                padding = max(8, math.ceil(size * .4)) + (3 if kind == "sfx" else 0)
                if explicit:
                    allocation = explicit
                else:
                    factor = _factors(kind)
                    max_w = min(width - margin * 2, max(96, math.floor(width * .46)))
                    max_text_w = math.floor((max_w - 2 * padding) * factor)
                    try:
                        lines = wrap_text(text, font, max_text_w)
                    except BubbleLayoutError:
                        continue
                    tw, th, _ = _text_metrics(font, lines)
                    bw = max(50, math.ceil(tw / factor + 2 * padding + 2))
                    bh = math.ceil(th / factor + 2 * padding + 2)
                    if kind in {"normal", "thought"}:
                        bh = math.ceil(bh / .84) + 2
                    allocation = _place(position, bw, bh, width, height, margin, occupied)
                    if allocation is None:
                        continue
                body = _body(allocation, kind)
                content = _content_box(body, kind, padding)
                try:
                    lines = wrap_text(text, font, math.floor(content[2] - content[0]))
                except BubbleLayoutError:
                    continue
                tw, th, line_height = _text_metrics(font, lines)
                if th > content[3] - content[1]:
                    continue
                tail = _tail_points(body, allocation, target, kind)
                footprint = _footprint(allocation, tail)
                if kind == "thought" and tail:
                    for x, y, radius in _thought_dots(body, tail):
                        footprint = (min(footprint[0], x - radius), min(footprint[1], y - radius),
                                     max(footprint[2], x + radius), max(footprint[3], y + radius))
                if footprint[0] < 0 or footprint[1] < 0 or footprint[2] > width or footprint[3] > height:
                    continue
                if any(_overlaps(footprint, other) for other in occupied):
                    continue
                fitted = (body, content, tail, footprint, font, lines, th, line_height)
                break
            if fitted is None:
                raise BubbleLayoutError(
                    f"Cannot fit/place text at {min_font_size}px or larger. "
                    "Enlarge/change box or position, shorten/split dialogue, or use a taller cut. "
                    "Boxes and tail footprints must stay inside the image and must not overlap."
                )
            body, content, tail, footprint, font, lines, th, line_height = fitted
            occupied.append(footprint)
            outline = max(2, min(4, round(width / 300)))
            _draw_shape(draw, body, kind, tail, outline)
            y = (content[1] + content[3] - th) / 2
            for line in lines:
                bbox = font.getbbox(line)
                ink_width = bbox[2] - bbox[0]
                x = (content[0] + content[2] - ink_width) / 2 - bbox[0]
                # ascender anchor + full metrics line box prevent baseline
                # offsets from clipping Korean glyphs or Latin descenders.
                draw.text((x, y), line, font=font, fill="black", anchor="lt",
                          stroke_width=3 if kind == "sfx" else 0,
                          stroke_fill="white" if kind == "sfx" else None)
                y += line_height
        except BubbleLayoutError as error:
            raise BubbleLayoutError(f"Dialogue {index + 1}: {error}") from error
    return Image.alpha_composite(result, overlay).convert(output_mode)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("dialogue", type=Path, help="JSON dialogue list, or object with dialogue list")
    parser.add_argument("output", type=Path)
    parser.add_argument("--font", type=Path)
    parser.add_argument("--font-size", type=int, default=30)
    parser.add_argument("--min-font-size", type=int, default=16)
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.dialogue.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            data = data.get("dialogue", data.get("dialogues"))
        with Image.open(args.image) as source:
            rendered = render_bubbles(source, data, font_path=args.font,
                                      font_size=args.font_size, min_font_size=args.min_font_size)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        rendered.save(args.output)
        assert args.output.is_file() and args.output.stat().st_size > 0, "Missing/empty lettered image"
        with Image.open(args.output) as saved:
            assert saved.size == rendered.size, "Unexpected lettered image dimensions"
            saved.verify()
    except (OSError, ValueError) as error:
        parser.exit(2, f"bubble_renderer: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
