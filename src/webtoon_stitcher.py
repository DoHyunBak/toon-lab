"""Aspect-preserving vertical compositor with cuts kept whole in upload slices.

Adapted from manga-studio/assemble_pages.py (assemble_page's Pillow compositing
and output stages), MIT, Copyright (c) 2026 ahmet360. See THIRD_PARTY_NOTICES.md.
The print grid, fixed page height, cover_crop and missing-art placeholders are
replaced with ordered full-width cuts, explicit whitespace and hard failures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from PIL import Image, ImageColor, ImageOps

from .bubble_renderer import render_bubbles
from .font_policy import episode_fonts, write_font_notices, source_font_records

WIDTH = 800


def _integer(value, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_image(path: Path, size: tuple[int, int]) -> None:
    assert path.is_file() and path.stat().st_size > 0, f"Missing/empty image: {path}"
    with Image.open(path) as image:
        assert image.size == size, f"Unexpected image dimensions: {path}"
        image.verify()


def _smart_slices(height: int, cuts: list[dict], max_height: int) -> list[tuple[int, int]]:
    gaps = [(0, cuts[0]["y"])]
    for index, cut in enumerate(cuts):
        next_y = cuts[index + 1]["y"] if index + 1 < len(cuts) else height
        gaps.append((cut["y"] + cut["height"], next_y))
    slices = []
    start = 0
    while start < height:
        limit = min(start + max_height, height)
        candidates = [min(end, limit) for begin, end in gaps
                      if begin <= limit and min(end, limit) > start]
        if not candidates:
            cut = next(c for c in cuts if c["y"] <= start < c["y"] + c["height"])
            raise ValueError(f"{cut['id']}: cut height {cut['height']} exceeds --max-height {max_height}; "
                             "increase the limit or resize/edit this cut. Cuts are never sliced through.")
        end = max(candidates)
        slices.append((start, end))
        start = end
    return slices


def stitch_episode(
    manifest_path: str | Path,
    output_dir: str | Path,
    *,
    width: int = WIDTH,
    padding: int = 120,
    top_padding: int = 100,
    bottom_padding: int = 100,
    max_height: int = 4000,
    background: str = "#FFFFFF",
    font_path: str | Path | None = None,
    font_size: int = 30,
    min_font_size: int = 16,
    max_pixels: int = 100_000_000,
    overwrite: bool = False,
) -> Path:
    """Write full_strip.png, slice_NNN.png and a hashed, ordered output manifest.

    Input paths are relative to the input JSON. Art is scaled without cropping;
    lettering is applied AFTER resizing. The final cut has no automatic gap.
    Slices cover [0,height) exactly and end only in gutters or at cut edges.
    A single cut taller than max_height is rejected with an actionable error.
    Existing output is protected unless overwrite=True. Only files listed in
    this engine's previous manifest can be removed during a repeated run.
    """
    for name, value in (("padding", padding), ("top_padding", top_padding),
                        ("bottom_padding", bottom_padding)):
        _integer(value, name)
    _integer(max_height, "max_height", 1)
    _integer(width, "width", 1)
    if not isinstance(background, str):
        raise ValueError("background must be a Pillow color string such as #FFFFFF or #000000")
    color = ImageColor.getcolor(background, "RGB")
    _integer(max_pixels, "max_pixels", 1)
    _integer(font_size, "font_size", 1)
    _integer(min_font_size, "min_font_size", 1)
    if min_font_size > font_size:
        raise ValueError("min_font_size cannot exceed font_size")
    source = Path(manifest_path).resolve()
    episode = json.loads(source.read_text(encoding="utf-8-sig"))
    if not isinstance(episode, dict) or not isinstance(episode.get("cuts"), list) or not episode["cuts"]:
        raise ValueError("Manifest must contain a non-empty cuts list")
    fonts = episode_fonts(episode, font_path)
    output = Path(output_dir).resolve()
    old_paths: set[Path] = set()
    old_manifest = output / "manifest.json"
    if old_manifest.exists():
        if not overwrite:
            raise FileExistsError(f"Output already exists: {output}; use --overwrite")
        previous = json.loads(old_manifest.read_text(encoding="utf-8"))
        if previous.get('font_policy') == 'open-fonts-v1':
            source_font_records(output, previous)
        if (previous.get("generator") != "webtoon-factory" or previous.get("schema_version") != 1
                or not isinstance(previous.get("full"), dict)
                or previous["full"].get("path") not in {"full_strip.png", "full.png"}
                or not isinstance(previous.get("parts"), list)):
            raise ValueError("Refusing to overwrite an invalid or unowned output manifest")
        for index, item in enumerate([previous["full"], *previous["parts"]]):
            relative = item["path"]
            if (not isinstance(relative, str) or (index and not re.fullmatch(
                    r"slice_\d{3,}\.png|parts/part_\d{3,}\.png", relative))
                    or not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", ""))):
                raise ValueError("Previous manifest contains an unsafe output path")
            old = output / relative
            if (not old.resolve().is_relative_to(output) or old.is_symlink()
                    or old.parent.is_symlink()):
                raise ValueError(f"Refusing linked output outside the output directory: {old}")
            if old.exists() and _digest(old) != item["sha256"]:
                raise ValueError(f"Output was modified after generation: {old}; choose a new output directory")
            old_paths.add(old)

    for name in ['font_licenses.json', 'licenses/Pretendard-OFL.txt']:
        target = output / name
        if target.is_symlink() or target.parent.is_symlink():
            raise ValueError(f'Refusing symlink output: {target}')
        if target.exists() and not (old_manifest.exists() and previous.get('font_policy') == 'open-fonts-v1'):
            raise FileExistsError(f'Refusing to replace an unowned file: {target}')

    specs = []
    seen = set()
    height = top_padding + bottom_padding
    for index, cut in enumerate(episode["cuts"]):
        if not isinstance(cut, dict):
            raise ValueError(f"Cut {index + 1} must be an object")
        cut_id = cut.get("id")
        if not isinstance(cut_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", cut_id):
            raise ValueError("Every cut needs an id starting with an ASCII letter/number, followed by letters, numbers, _, . or -")
        if cut_id in seen:
            raise ValueError(f"Duplicate cut id: {cut_id}")
        seen.add(cut_id)
        if not isinstance(cut.get("image"), str) or not cut["image"]:
            raise ValueError(f"{cut_id}: image is missing; render or import the cut first")
        path = (source.parent / cut["image"]).resolve()
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            size = image.size
        display_width = cut.get("display_width", width)
        _integer(display_width, f"{cut_id}.display_width", 1)
        if display_width > width:
            raise ValueError(f"{cut_id}: display_width exceeds the canvas width")
        x = cut.get("x", (width - display_width) // 2)
        _integer(x, f"{cut_id}.x")
        if x + display_width > width:
            raise ValueError(f"{cut_id}: x + display_width exceeds the canvas width")
        target_h = max(1, round(size[1] * display_width / size[0]))
        gap = cut.get("gap_after", padding) if index < len(episode["cuts"]) - 1 else 0
        _integer(gap, f"{cut_id}.gap_after")
        ImageColor.getrgb(cut.get("matte", background))
        gradient = cut.get("gap_gradient_after")
        if gradient is not None:
            if not isinstance(gradient, list) or len(gradient) != 2:
                raise ValueError(f"{cut_id}: gap_gradient_after needs two colors")
            for endpoint in gradient:
                ImageColor.getrgb(endpoint)
        specs.append((cut, path, target_h, gap, display_width, x))
        height += target_h + gap
    if width * height > max_pixels:
        raise ValueError(f"Full strip requires {width * height:,} pixels; limit is {max_pixels:,}. "
                         "Split the episode or deliberately increase --max-pixels")

    cut_positions = []
    position = top_padding
    for cut, _, cut_height, gap, _, _ in specs:
        cut_positions.append({"id": cut["id"], "y": position, "height": cut_height})
        position += cut_height + gap
    ranges = _smart_slices(height, cut_positions, max_height)
    new_paths = {output / "full_strip.png", *(output / f"slice_{i:03d}.png"
                                            for i in range(1, len(ranges) + 1))}
    for target in new_paths:
        if target.is_symlink() or target.parent.is_symlink():
            raise ValueError(f"Refusing symlink output: {target}")
        if target.exists() and target not in old_paths:
            raise FileExistsError(f"Refusing to replace an unowned file: {target}")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Stage all images before publishing, so bad text or a missing font produces
    # no partly lettered deliverable. A failed run preserves prior output.
    with tempfile.TemporaryDirectory(prefix="webtoon-", dir=output.parent) as temp:
        stage = Path(temp)
        full = Image.new("RGB", (width, height), color)
        y = top_padding
        cut_records = []
        for cut, path, target_h, gap, display_width, x in specs:
            with Image.open(path) as raw:
                art = ImageOps.exif_transpose(raw).convert("RGBA")
                art = art.resize((display_width, target_h), Image.Resampling.LANCZOS)
                base = Image.new("RGBA", art.size, ImageColor.getrgb(cut.get("matte", background)))
                art = Image.alpha_composite(base, art).convert("RGB")
            dialogue = cut.get("dialogue", [])
            if not isinstance(dialogue, list):
                raise ValueError(f"{cut['id']}: dialogue must be a list")
            try:
                lettered = render_bubbles(art, dialogue, font_path=font_path,
                                          font_size=font_size, min_font_size=min_font_size)
            except (ValueError, OSError) as error:
                raise ValueError(f"{cut['id']}: {error}") from error
            full.paste(lettered, (x, y))
            cut_records.append({"id": cut["id"], "x": x, "width": display_width, "y": y, "height": target_h,
                                "gap_after": gap, "source_sha256": _digest(path)})
            if "matte" in cut:
                cut_records[-1]["matte"] = cut["matte"]
            gradient = cut.get("gap_gradient_after")
            if gradient is not None and gap:
                start, end = (ImageColor.getrgb(v) for v in gradient)
                for row in range(gap):
                    t = row / max(1, gap - 1)
                    t = t * t * (3 - 2 * t)
                    shade = tuple(round(a + (b - a) * t) for a, b in zip(start, end))
                    full.paste(shade, (0, y + target_h + row, width, y + target_h + row + 1))
                cut_records[-1]["gap_gradient_after"] = gradient
            y += target_h + gap
        full.save(stage / "full_strip.png")
        _verify_image(stage / "full_strip.png", (width, height))
        parts = []
        for index, (start, end) in enumerate(ranges, 1):
            name = f"slice_{index:03d}.png"
            full.crop((0, start, width, end)).save(stage / name)
            _verify_image(stage / name, (width, end - start))
            parts.append({"path": name, "y": start, "height": end - start,
                          "sha256": _digest(stage / name)})
        write_font_notices(stage, fonts)
        result = {"generator": "webtoon-factory", "schema_version": 1,
                  "font_policy": "open-fonts-v1", "fonts_used": fonts,
                  "font_licenses_sha256": _digest(stage / 'font_licenses.json'),
                  "title": episode.get("title", "Untitled"),
                  "width": width, "height": height, "max_part_height": max_height,
                  "background": background, "split_mode": "gutters_only",
                  "source_manifest_sha256": _digest(source),
                  "full": {"path": "full_strip.png", "sha256": _digest(stage / "full_strip.png")},
                  "cuts": cut_records, "parts": parts,
                  "note": "PNG slices are lossless; platform byte limits require separate verification."}
        (stage / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
        assert (stage / "manifest.json").stat().st_size > 0
        output.mkdir(parents=True, exist_ok=True)
        if fonts:
            (output / 'licenses').mkdir(exist_ok=True)
            os.replace(stage / 'licenses/Pretendard-OFL.txt', output / 'licenses/Pretendard-OFL.txt')
        os.replace(stage / 'font_licenses.json', output / 'font_licenses.json')
        for record in [result["full"], *parts]:
            name = record["path"]
            os.replace(stage / name, output / name)
        for stale in old_paths - new_paths:
            stale.unlink(missing_ok=True)
        os.replace(stage / "manifest.json", old_manifest)
        assert old_manifest.is_file() and old_manifest.stat().st_size > 0
    return old_manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--width", type=int, default=WIDTH)
    parser.add_argument("--padding", type=int, default=120)
    parser.add_argument("--background", default="#FFFFFF")
    parser.add_argument("--top-padding", type=int, default=100)
    parser.add_argument("--bottom-padding", type=int, default=100)
    parser.add_argument("--max-height", type=int, default=4000)
    parser.add_argument("--font", type=Path)
    parser.add_argument("--font-size", type=int, default=30)
    parser.add_argument("--min-font-size", type=int, default=16)
    parser.add_argument("--max-pixels", type=int, default=100_000_000)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = stitch_episode(args.manifest, args.output_dir, width=args.width, padding=args.padding,
                                background=args.background,
                                top_padding=args.top_padding, bottom_padding=args.bottom_padding,
                                max_height=args.max_height, font_path=args.font, font_size=args.font_size,
                                min_font_size=args.min_font_size, max_pixels=args.max_pixels,
                                overwrite=args.overwrite)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, f"stitch failed: {error}\n")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
