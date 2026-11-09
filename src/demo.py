"""Create ten clearly marked mock cut/atari/background trios and assemble them.

These primitives exercise file handling and lettering only. Mock guides are
NOT preprocessed ControlNet inputs and must be replaced before real rendering.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from PIL import Image, ImageDraw, ImageFont

from .bubble_renderer import render_bubbles
from .script_formatter import format_script, validate_episode
from .webtoon_stitcher import stitch_episode


def _safe_path(candidate: Path, root: Path) -> Path:
    """Reject escapes and links before resolving the output path."""
    for component in [candidate, *candidate.parents]:
        if component.is_symlink() or (hasattr(component, "is_junction") and component.is_junction()):
            raise ValueError(f"Demo refuses linked paths: {component}")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root.resolve()) or resolved == root.resolve():
        raise ValueError(f"Demo output must stay inside {root}: {candidate}")
    return resolved


def _check_write_target(path: Path, overwrite: bool):
    if path.exists():
        if not path.is_file():
            raise ValueError(f"Demo target is not a file: {path}")
        if not overwrite:
            raise FileExistsError(f"Demo artifact exists: {path}; use --overwrite")


def _mock_art(index: int, cut_id: str) -> Image.Image:
    palettes = ["#cddbd5", "#ccd7df", "#ded5c8", "#d1d4dc", "#d6ddc8"]
    h = 560 if index % 2 == 0 else 440
    image = Image.new("RGB", (800, h), palettes[index % len(palettes)])
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 210, 720, h - 30), outline="#40494a", width=4)
    draw.line((80, h - 30, 260, 240, 540, 240, 720, h - 30), fill="#8b9997", width=3)
    draw.ellipse((352, 250, 448, 346), fill="#f3ddc4", outline="#40494a", width=3)
    draw.polygon([(365, 350), (435, 350), (470, h - 45), (330, h - 45)],
                 fill="#728b7e", outline="#40494a")
    draw.text((18, h - 27), f"OFFLINE PLACEHOLDER / {cut_id} / NOT AI RENDER",
              fill="#172724", font=ImageFont.load_default(size=18))
    return image


def _mock_guide(index: int, cut_id: str, role: str) -> Image.Image:
    image = Image.new("RGB", (768, 1024), "#e9eceb" if role == "atari" else "white")
    draw = ImageDraw.Draw(image)
    if role == "atari":
        # Deliberately schematic; no claim of an OpenPose/DWPose encoding.
        x = 340 + (index % 3) * 35
        draw.ellipse((x - 48, 260, x + 48, 356), outline="#45555e", width=7)
        for endpoints in [((x, 356), (x, 650)), ((x, 410), (x - 130, 550)),
                          ((x, 410), (x + 110, 500 - (index % 2) * 100)),
                          ((x, 650), (x - 90, 875)), ((x, 650), (x + 100, 875))]:
            draw.line(endpoints, fill="#576e88", width=10)
        for y in (356, 410, 650):
            draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill="#c18366")
    else:
        vanish = (350 + (index % 3) * 25, 540)
        draw.rectangle((120, 280, 648, 800), outline="#40494a", width=5)
        for corner in ((0, 100), (768, 100), (0, 1024), (768, 1024)):
            draw.line((corner, vanish), fill="#72817e", width=3)
        draw.rectangle((300, 430, 450, 800), outline="#40494a", width=4)
    font = ImageFont.load_default(size=20)
    draw.text((20, 20), f"OFFLINE {role.upper()} MOCK / {cut_id}", font=font, fill="#172724")
    draw.text((20, 52), "NOT A PREPROCESSED CONTROLNET GUIDE", font=font, fill="#842d2d")
    return image


def _verify_image(path: Path, *, width: int, height: int | None = None):
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Missing/empty demo artifact: {path}")
    with Image.open(path) as image:
        image.load()
        if image.width != width or (height is not None and image.height != height):
            raise RuntimeError(f"Wrong demo image dimensions: {path}: {image.size}")


def run_demo(workspace: str | Path, *, font_path=None, overwrite=False) -> Path:
    workspace = Path(workspace).resolve()
    source = workspace / "01_scripts" / "example.json"
    # Validate the WHOLE episode before creating or overwriting any artifact.
    episode = validate_episode(json.loads(source.read_text(encoding="utf-8-sig")))
    if len(episode["cuts"]) != 10:
        raise ValueError("The offline demo requires exactly ten cuts in example.json")
    roots = {"image": workspace / "05_rendered_cuts" / "demo",
             "atari": workspace / "02_conti_atari" / "demo",
             "background": workspace / "03_backgrounds" / "demo"}
    demo_source = _safe_path(source.parent / "demo_source.json", workspace)
    batches = _safe_path(source.parent / "demo_chunks", workspace)
    output = _safe_path(workspace / "06_output_webtoon" / "demo", workspace)
    _check_write_target(demo_source, overwrite)
    if not overwrite and ((batches.exists() and any(batches.iterdir())) or (output / "manifest.json").exists()):
        raise FileExistsError("Demo batches/output already exist; use --overwrite")
    planned = []
    seen = set()
    for index, cut in enumerate(episode["cuts"]):
        if not cut.get("image"):
            raise ValueError(f"{cut['id']}: demo image path is required")
        raw = _safe_path(source.parent / cut["image"], roots["image"])
        assets = {"image": raw,
                  "atari": _safe_path(roots["atari"] / f"{cut['id']}.png", roots["atari"]),
                  "background": _safe_path(roots["background"] / f"{cut['id']}.png", roots["background"])}
        for role, target in assets.items():
            if target.suffix.lower() != ".png":
                raise ValueError(f"Demo assets must use PNG paths: {target}")
            if target in seen:
                raise ValueError(f"Duplicate demo image path: {target}")
            seen.add(target)
            _check_write_target(target, overwrite)
            cut[role] = Path(os.path.relpath(target, source.parent)).as_posix()
        # These are file-I/O mocks, deliberately excluded from any real GPU claim.
        cut["demo_placeholder"] = True
        cut["controls"] = []
        planned.append((index, cut, assets))
    episode["demo_mode"] = True
    episode["guide_warning"] = "OFFLINE MOCKS ONLY: replace atari/background with compatible preprocessed guides before real ComfyUI rendering."
    payload = json.dumps(episode, ensure_ascii=False, indent=2) + "\n"

    # Catch native-script errors, bad fonts and impossible balloons BEFORE any
    # existing demo image is replaced. The temporary formatter output is private.
    pending = []
    with tempfile.TemporaryDirectory(prefix="demo-preflight-", dir=workspace) as temp:
        check_source = Path(temp) / "demo_source.json"
        check_source.write_text(payload, encoding="utf-8")
        format_script(check_source, Path(temp) / "batches")
        for index, cut, assets in planned:
            art = _mock_art(index, cut["id"])
            render_bubbles(art, cut["dialogue"], font_path=font_path)
            pending.extend([(assets["image"], art),
                            (assets["atari"], _mock_guide(index, cut["id"], "atari")),
                            (assets["background"], _mock_guide(index, cut["id"], "background"))])
    for target, image in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target)
        if target.is_relative_to(roots["image"].resolve()):
            _verify_image(target, width=800, height=560 if image.height == 560 else 440)
        else:
            _verify_image(target, width=768, height=1024)
    demo_source.write_text(payload, encoding="utf-8")
    index = format_script(demo_source, batches)
    result = stitch_episode(batches / index["episode"], output, width=800, padding=120,
                            max_height=4000, font_path=font_path, overwrite=overwrite)
    if not result.is_file() or result.stat().st_size == 0:
        raise RuntimeError("Demo output manifest is missing or empty")
    emitted = json.loads(result.read_text(encoding="utf-8"))
    if emitted.get("width") != 800 or len(emitted.get("cuts", [])) != 10:
        raise RuntimeError("Demo output width/cut count verification failed")
    if emitted.get("full", {}).get("path") != "full_strip.png":
        raise RuntimeError("Demo output must include full_strip.png")
    _verify_image(output / "full_strip.png", width=800, height=emitted["height"])
    if not emitted.get("parts"):
        raise RuntimeError("Demo output has no upload slices")
    next_y = 0
    for number, part in enumerate(emitted["parts"], 1):
        if part.get("path") != f"slice_{number:03d}.png" or part.get("y") != next_y:
            raise RuntimeError("Demo upload slices have invalid names or row coverage")
        if not 1 <= part.get("height", 0) <= 4000:
            raise RuntimeError("Demo slice exceeds the configured upload height")
        _verify_image(output / part["path"], width=800, height=part["height"])
        next_y += part["height"]
    if next_y != emitted["height"]:
        raise RuntimeError("Demo upload slices do not cover the full strip")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[1] / "workspace")
    parser.add_argument("--font", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        print(run_demo(args.workspace, font_path=args.font, overwrite=args.overwrite))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, f"demo failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
