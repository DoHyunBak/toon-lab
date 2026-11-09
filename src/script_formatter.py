"""Prepare a local cut manifest and native Comicalizer batches of at most two pages.

No story generation or browser automation is performed. Comicalizer's public
10_vocab.js / 37_help.js syntax was checked on 2026-10-16; the JSON manifest is
the lossless source of truth, while native text includes only supported tags.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any


DEFAULT_CAMERA = {"shot": "MS", "angle": "eye-level", "lens": "50mm", "position": "front"}
VALID_POSITIONS = {"auto", "top-left", "top-right", "bottom-left", "bottom-right", "top", "bottom", "center"}
VALID_TYPES = {"normal", "shout", "thought", "narration", "sfx"}
_PAGE = re.compile(r"^#{0,6}\s*(?:(?:PAGE|페이지|ページ)\s*:?\s*(\d+)|(\d+)\s*(?:P|페이지|ページ))\s*:?\s*$", re.I)
_TITLE = re.compile(r"^(?:TITLE|제목|タイトル)\s*[:：]\s*(.*)$", re.I)
_PANEL = re.compile(r"^(?:(?:CUT|PANEL|컷)\s*)?(\d+)\s*[:：.]\s*(.*)$", re.I)
_BRACKET = re.compile(r"\[([^\[\]]*)\]|［([^［］]*)］")
_SPEECH = re.compile(r'([^\s「」“”"()（）]+)\s*[:：]?\s*(?:「([^」]*)」|“([^”]*)”|"([^"\n]*)"|（([^）]*)）)')
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class ScriptError(ValueError):
    """Invalid or ambiguous script input."""


def _key(value: str) -> str:
    return re.sub(r"[\s_・-]+", "", value).casefold()


def _vocabulary(entries: list[tuple[str, tuple[str, ...]]]) -> dict[str, str]:
    return {_key(alias): native for native, aliases in entries for alias in (native, *aliases)}


# Verified public vocabulary; original user metadata is never replaced by these aliases.
_TAGS = {
    "shot": _vocabulary([
        ("エクストリーム・ロングショット", ("ELS", "XLS", "EWS", "extreme long shot", "extreme wide shot", "익스트림 롱숏")),
        ("ロングショット", ("LS", "WS", "long shot", "wide shot", "롱숏", "와이드 숏")),
        ("フルショット", ("FS", "full shot", "풀숏", "풀 샷")),
        ("ニーショット", ("KS", "MLS", "knee shot", "medium long shot", "니숏")),
        ("ウエストショット", ("MS", "medium shot", "waist shot", "미디엄 숏")),
        ("バストショット", ("MCU", "medium close-up", "바스트 숏")),
        ("クローズアップ", ("CU", "close-up", "closeup", "클로즈업")),
        ("エクストリーム・クローズアップ", ("ECU", "XCU", "extreme close-up", "익스트림 클로즈업")),
    ]),
    "angle": _vocabulary([
        ("バーズアイビュー", ("bird's-eye view", "birds eye view", "overhead shot", "top shot", "버즈 아이 뷰")),
        ("ハイアングル", ("high angle", "하이 앵글", "부감")),
        ("ややハイアングル", ("slight high angle",)),
        ("アイレベル", ("eye level", "아이 레벨", "눈높이")),
        ("ローアングル", ("low angle", "로우 앵글")),
        ("ワームズアイビュー", ("worm's-eye view", "worms eye view", "웜즈 아이 뷰")),
        ("ローポジション", ("low position",)),
        ("ハイポジション", ("high position",)),
    ]),
    "position": _vocabulary([
        ("正面", ("front", "정면")),
        ("スリークォーター", ("three-quarter", "3/4", "사선 정면")),
        ("真横", ("profile", "side", "측면")),
        ("斜め後ろ", ("three-quarter back",)),
        ("後ろから", ("from behind", "back", "후면")),
    ]),
    "lens": _vocabulary([
        ("超広角レンズ", ("ultra-wide", "ultra-wide lens", "fisheye", "초광각")),
        ("広角レンズ", ("wide-angle", "wide-angle lens", "wide lens", "광각")),
        ("標準レンズ", ("normal lens", "standard lens", "standard", "표준")),
        ("望遠レンズ", ("telephoto", "telephoto lens", "망원")),
        ("超望遠レンズ", ("super telephoto", "super-telephoto lens", "초망원")),
    ]),
}


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ScriptError(f"{label} must be a positive integer")
    return value


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScriptError(f"{label} must be a nonempty string")
    return value.strip()


def validate_episode(data: Any, cuts_per_page: int = 4) -> dict[str, Any]:
    """Normalize the shared manifest without discarding extra rendering fields."""
    _positive_int(cuts_per_page, "cuts_per_page")
    if not isinstance(data, dict):
        raise ScriptError("episode must be a JSON object containing cuts")
    episode = copy.deepcopy(data)
    episode["title"] = _nonempty(episode.get("title", "Untitled"), "title")
    cuts = episode.get("cuts")
    if not isinstance(cuts, list) or not cuts:
        raise ScriptError("cuts must be a nonempty list")
    explicit = [isinstance(cut, dict) and "page" in cut for cut in cuts]
    if any(explicit) and not all(explicit):
        raise ScriptError("provide page for every cut, or omit page for every cut")
    seen: set[str] = set()
    page_counts: dict[int, int] = {}
    previous_page = 0
    for index, cut in enumerate(cuts):
        label = f"cut {index + 1}"
        if not isinstance(cut, dict):
            raise ScriptError(f"{label} must be an object")
        identifier = _nonempty(cut.get("id", f"cut_{index + 1:03d}"), f"{label}.id")
        if not _ID.fullmatch(identifier) or identifier.endswith("."):
            raise ScriptError(f"{label}.id must use letters, digits, underscores, dots or hyphens")
        if identifier in seen:
            raise ScriptError(f"duplicate cut id: {identifier}")
        seen.add(identifier)
        cut["id"] = identifier
        page = _positive_int(cut.get("page", index // cuts_per_page + 1), f"{identifier}.page")
        if page < previous_page:
            raise ScriptError("cut pages must be in ascending order; a closed page cannot reappear")
        previous_page = cut["page"] = page
        page_counts[page] = page_counts.get(page, 0) + 1
        if page_counts[page] > cuts_per_page:
            raise ScriptError(f"page {page} exceeds cuts_per_page={cuts_per_page}; split the page explicitly")
        cut["description"] = _nonempty(cut.get("description", cut.get("prompt")), f"{identifier}.description")
        camera = cut.get("camera", {})
        if not isinstance(camera, dict):
            raise ScriptError(f"{identifier}.camera must be an object")
        cut["camera"] = {**DEFAULT_CAMERA, **camera}
        for field in DEFAULT_CAMERA:
            cut["camera"][field] = _nonempty(cut["camera"][field], f"{identifier}.camera.{field}")
        characters = cut.setdefault("characters", [])
        if not isinstance(characters, list) or any(not isinstance(char, str) or not char.strip() for char in characters):
            raise ScriptError(f"{identifier}.characters must be a list of nonempty strings")
        if len(set(characters)) != len(characters):
            raise ScriptError(f"{identifier}.characters contains duplicate names")
        dialogue = cut.setdefault("dialogue", [])
        if not isinstance(dialogue, list):
            raise ScriptError(f"{identifier}.dialogue must be a list")
        for bubble in dialogue:
            if not isinstance(bubble, dict):
                raise ScriptError(f"{identifier}.dialogue entries must be objects")
            if not isinstance(bubble.setdefault("speaker", ""), str):
                raise ScriptError(f"{identifier}.dialogue speaker must be a string")
            bubble["text"] = _nonempty(bubble.get("text"), f"{identifier}.dialogue text")
            if bubble.setdefault("position", "auto") not in VALID_POSITIONS:
                raise ScriptError(f"{identifier}: invalid dialogue position")
            if bubble.setdefault("type", "normal") not in VALID_TYPES:
                raise ScriptError(f"{identifier}: invalid dialogue type")
        for field in ("image", "atari", "background", "prompt"):
            if field in cut:
                cut[field] = _nonempty(cut[field], f"{identifier}.{field}")
        if "gap_after" in cut and (isinstance(cut["gap_after"], bool) or not isinstance(cut["gap_after"], int) or cut["gap_after"] < 0):
            raise ScriptError(f"{identifier}.gap_after must be a nonnegative integer")
        if "controls" in cut:
            if not isinstance(cut["controls"], list) or any(not isinstance(control, dict) for control in cut["controls"]):
                raise ScriptError(f"{identifier}.controls must be a list of objects")
            for control in cut["controls"]:
                if "image" in control:
                    control["image"] = _nonempty(control["image"], f"{identifier}.controls image")
    return episode


def _camera_tags(line: str) -> tuple[str, dict[str, str]]:
    camera: dict[str, str] = {}

    def read(match: re.Match[str]) -> str:
        body = match.group(1) if match.group(1) is not None else match.group(2)
        parts = [part.strip() for part in re.split(r"[,、，]", body)]
        if len(parts) == 4 and "=" not in body:
            if not all(parts):
                raise ScriptError("manual camera tags require four nonempty values: shot, angle, lens, position")
            camera.update(dict(zip(DEFAULT_CAMERA, parts)))
            return ""
        # Native supported words, including tags produced by this module.
        recognized = 0
        for part in parts:
            for field, words in _TAGS.items():
                if _key(part) in words:
                    camera[field] = part
                    recognized += 1
                    break
        detail = re.match(r"^(?:カメラ|Camera)\s+(.+)$", body, re.I)
        if detail:
            lens = re.search(r"(?:レンズ|lens)=([-+\d.]+)(?:mm)?", detail.group(1), re.I)
            position = re.search(r"(?:位置|pos)=([-+\d.,]+)", detail.group(1), re.I)
            if lens:
                camera["lens"] = lens.group(1) + "mm"
            if position:
                camera["position"] = position.group(1)
            return ""
        return "" if recognized == len(parts) else match.group(0)

    return _BRACKET.sub(read, line).strip(), camera


def parse_script(text: str, cuts_per_page: int = 4) -> dict[str, Any]:
    """Parse UTF-8 text/JSON. Plain nonempty lines are cuts, unless page headers delimit them.

    Manual camera order: [shot, angle, lens, position]. Plain dialogue may use
    민수「안녕」 or 민수: "안녕". JSON is required for precise bubble placement
    and rendering assets. Explicit PAGE: n / nP boundaries are never repaginated.
    """
    _positive_int(cuts_per_page, "cuts_per_page")
    if not isinstance(text, str):
        raise ScriptError("text must be a string")
    text = text.lstrip("\ufeff")
    if text.lstrip().startswith(("{", "[")):
        # A leading camera tag is plain text, not a JSON array.
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            if text.lstrip().startswith("{"):
                raise ScriptError(f"invalid JSON: {error}") from error
        else:
            return validate_episode(data, cuts_per_page)
    cuts: list[dict[str, Any]] = []
    title = "Untitled"
    current_page: int | None = None
    page_seen: set[int] = set()
    page_has_cut = False
    panel_seen: set[int] = set()
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        title_match = _TITLE.match(line)
        if title_match:
            title = _nonempty(title_match.group(1), f"line {lineno} title")
            continue
        page_match = _PAGE.match(line.replace("：", ":"))
        if page_match:
            page = int(page_match.group(1) or page_match.group(2))
            _positive_int(page, f"line {lineno} page")
            if cuts and current_page is None:
                raise ScriptError(f"line {lineno}: explicit pages cannot follow unpaginated cuts")
            if current_page is not None and not page_has_cut:
                raise ScriptError(f"empty page: {current_page}")
            if page in page_seen or (current_page is not None and page < current_page):
                raise ScriptError(f"duplicate or out-of-order page: {page}")
            page_seen.add(page)
            current_page, page_has_cut, panel_seen = page, False, set()
            continue
        if re.match(r"^#{0,6}\s*(?:PAGE|페이지|ページ)(?:\s|:|$)|^\d+\s*P\b", line, re.I):
            raise ScriptError(f"line {lineno}: malformed page header")
        if line.startswith("#") or re.match(r"^(?:登場人物|読む向き|最初のページ|言語)\s*[:：]", line):
            continue
        panel_match = _PANEL.match(line)
        if panel_match:
            number = int(panel_match.group(1))
            _positive_int(number, f"line {lineno} cut number")
            if number in panel_seen:
                raise ScriptError(f"line {lineno}: duplicate cut number {number} within page")
            panel_seen.add(number)
            line = _nonempty(panel_match.group(2), f"line {lineno} cut")
        description, camera = _camera_tags(line)
        description = _nonempty(description, f"line {lineno} description")
        dialogue, characters = [], []
        for speech in _SPEECH.finditer(description):
            speaker = speech.group(1).rstrip(":：")
            body = next(group for group in speech.groups()[1:] if group is not None)
            if not body.strip():
                raise ScriptError(f"line {lineno}: empty dialogue")
            dialogue.append({"speaker": speaker, "text": body.replace("\\n", "\n"), "position": "auto", "type": "thought" if speech.group(5) is not None else "normal"})
            if speaker not in characters:
                characters.append(speaker)
        cut = {"id": f"cut_{len(cuts) + 1:03d}", "page": current_page or len(cuts) // cuts_per_page + 1,
               "description": description, "camera": camera, "characters": characters, "dialogue": dialogue}
        cuts.append(cut)
        page_has_cut = True
        if current_page is None and len(cuts) % cuts_per_page == 0:
            panel_seen = set()
    if current_page is not None and not page_has_cut:
        raise ScriptError(f"empty page: {current_page}")
    return validate_episode({"title": title, "cuts": cuts}, cuts_per_page)


def _native_camera(cut: dict[str, Any], warnings: list[str]) -> str:
    tags, details = [], []
    for field, value in cut["camera"].items():
        if field not in _TAGS:
            continue
        native = _TAGS[field].get(_key(value))
        if native:
            tags.append(native)
            continue
        if field == "lens" and re.fullmatch(r"\d+(?:\.\d+)?\s*mm", value, re.I):
            if float(re.sub(r"\s*mm$", "", value, flags=re.I)) > 0:
                details.append("レンズ=" + value.replace(" ", ""))
                continue
        if field == "position":
            coords = re.split(r"[,\s]+", value.strip("() "))
            try:
                valid = len(coords) == 3 and all(math.isfinite(float(coord)) for coord in coords)
            except ValueError:
                valid = False
            if valid:
                details.append("位置=" + ",".join(coords))
                continue
        warnings.append(f"{cut['id']}: camera.{field}={value!r} preserved in JSON; no verified native tag")
    return ("［" + "、".join(tags) + "］" if tags else "") + ("［カメラ " + " ".join(details) + "］" if details else "")


def _native_text(value: str, *, brackets: str = "") -> str:
    # Native syntax has no general quote escape: replace only delimiter characters.
    value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", r"\n")
    for char in brackets:
        value = value.replace(char, {"「": "『", "」": "』", "（": "(", "）": ")", "【": "〔", "】": "〕", "《": "〈", "》": "〉"}.get(char, char))
    return value


def _native_batch(episode: dict[str, Any], cuts: list[dict[str, Any]], pages: list[int], warnings: list[str]) -> str:
    characters = list(dict.fromkeys(char for cut in cuts for char in [*cut["characters"], *(bubble["speaker"] for bubble in cut["dialogue"] if bubble["speaker"] and bubble["type"] not in {"narration", "sfx"})]))
    lines = ["タイトル：" + _native_text(episode["title"]), "読む向き：左から", "最初のページ：右"]
    if characters:
        if any(any(char in name for char in "=,;、\n\r「」［］()（）") for name in characters):
            raise ScriptError("character names contain reserved Comicalizer delimiters")
        lines.append("登場人物：" + ", ".join(name + "=人形（160cm）" for name in characters))
    for local_page, global_page in enumerate(pages, 1):
        lines.extend(["", f"# 場面：ページ {global_page}", f"{local_page}P"])
        page_cuts = [cut for cut in cuts if cut["page"] == global_page]
        page_characters = {name for cut in page_cuts for name in [*cut["characters"], *(bubble["speaker"] for bubble in cut["dialogue"] if bubble["speaker"] and bubble["type"] not in {"narration", "sfx"})]}
        if len(page_characters) > 6:
            warnings.append(f"page {global_page}: more than six characters; Comicalizer supports at most six per page")
        for local_cut, cut in enumerate(page_cuts, 1):
            lines.append("// " + cut["id"] + " | " + _native_text(cut["description"]))
            body = []
            speaking = {bubble["speaker"] for bubble in cut["dialogue"] if bubble["type"] not in {"narration", "sfx"}}
            body.extend(name for name in cut["characters"] if name not in speaking)
            for bubble in cut["dialogue"]:
                kind, speaker, text = bubble["type"], bubble["speaker"], bubble["text"]
                left, right = {"thought": ("（", "）"), "narration": ("【", "】"), "sfx": ("《", "》")}.get(kind, ("「", "」"))
                body.append((speaker if kind not in {"narration", "sfx"} else "") + left + _native_text(text, brackets=left + right) + right + ("［叫び］" if kind == "shout" else ""))
            if not body:
                body.append("背景（" + _native_text(cut["description"], brackets="（）") + "）")
            lines.append(f"{local_cut}：" + "　".join(body) + _native_camera(cut, warnings))
    return "\n".join(lines) + "\n"


def _rebase_paths(episode: dict[str, Any], source: Path, destination: Path) -> None:
    def relative(value: str) -> str:
        path = Path(value)
        absolute = path if path.is_absolute() else source / path
        try:
            return Path(os.path.relpath(absolute.resolve(), destination.resolve())).as_posix()
        except ValueError:  # Windows: relative paths cannot cross drives.
            return str(absolute.resolve())

    for cut in episode["cuts"]:
        for field in ("image", "atari", "background"):
            if field in cut:
                cut[field] = relative(cut[field])
        for control in cut.get("controls", []):
            if "image" in control:
                control["image"] = relative(control["image"])


def format_script(input_path: str | Path, output_dir: str | Path, cuts_per_page: int = 4) -> dict[str, Any]:
    """Write episode.json, chunk_NN_pN-N.txt/.json and batches.json; return the index.

    Known stale chunks are removed only when their saved content digest matches.
    A changed or untracked stale chunk requires a fresh output directory.
    """
    source, destination = Path(input_path), Path(output_dir)
    text = source.read_text(encoding="utf-8-sig")
    if source.suffix.casefold() == ".json":
        try:
            episode = validate_episode(json.loads(text), cuts_per_page)
        except json.JSONDecodeError as error:
            raise ScriptError(f"invalid JSON: {error}") from error
    else:
        episode = parse_script(text, cuts_per_page)
    _rebase_paths(episode, source.resolve().parent, destination)
    pages = list(dict.fromkeys(cut["page"] for cut in episode["cuts"]))
    index: dict[str, Any] = {"title": episode["title"], "episode": "episode.json", "max_pages_per_batch": 2,
                             "max_cuts_per_batch": 2 * cuts_per_page, "batches": [], "warnings": []}
    outputs: dict[str, Any] = {"episode.json": episode}
    for offset in range(0, len(pages), 2):
        batch_pages = pages[offset:offset + 2]
        cuts = [cut for cut in episode["cuts"] if cut["page"] in batch_pages]
        if len(batch_pages) > 2 or len(cuts) > 2 * cuts_per_page:
            raise ScriptError("chunk exceeds its page or cut limit")
        stem = f"chunk_{offset // 2 + 1:02d}_p{batch_pages[0]}-{batch_pages[-1]}"
        batch = copy.deepcopy(episode)
        batch["cuts"] = copy.deepcopy(cuts)
        page_map = [{"local": local, "global": global_page} for local, global_page in enumerate(batch_pages, 1)]
        batch["global_pages"], batch["page_map"] = batch_pages, page_map
        for local_page, global_page in enumerate(batch_pages, 1):
            for local_cut, cut in enumerate((cut for cut in batch["cuts"] if cut["page"] == global_page), 1):
                cut["local_page"], cut["local_cut"] = local_page, local_cut
        outputs[stem + ".json"] = batch
        outputs[stem + ".txt"] = _native_batch(episode, cuts, batch_pages, index["warnings"])
        index["batches"].append({"id": stem, "text": stem + ".txt", "manifest": stem + ".json", "global_pages": batch_pages,
                                 "page_count": len(batch_pages), "page_map": page_map, "cut_ids": [cut["id"] for cut in cuts]})
    payloads = {filename: content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, indent=2) + "\n"
                for filename, content in outputs.items()}
    index["artifact_sha256"] = {filename: hashlib.sha256(payload.encode("utf-8")).hexdigest()
                                for filename, payload in payloads.items()}
    payloads["batches.json"] = json.dumps(index, ensure_ascii=False, indent=2) + "\n"
    for filename in payloads:
        target = (destination / filename).resolve()
        if target == source.resolve():
            raise ScriptError(f"output would overwrite source script: {source}")
        if target.parent != destination.resolve():
            raise ScriptError(f"output resolves outside output directory: {filename}")

    # Never erase hand edits or an unrelated similarly named file when the page
    # count shrinks. Only old index entries with matching digests are owned.
    stale: list[Path] = []
    generated_name = re.compile(r"(?:chunk_\d+_p\d+-\d+|batch_\d+)\.(?:txt|json)$")
    old_index_path = destination / "batches.json"
    old_digests: dict[str, str] = {}
    if old_index_path.exists():
        old_index = json.loads(old_index_path.read_text(encoding="utf-8"))
        if (not isinstance(old_index, dict) or old_index.get("episode") != "episode.json"
                or not isinstance(old_index.get("artifact_sha256"), dict)):
            raise ScriptError("existing batches.json is invalid; use a fresh output directory")
        old_digests = old_index.get("artifact_sha256", {})
    for filename in payloads:
        target = destination / filename
        if filename != "batches.json" and target.exists():
            if old_digests.get(filename) != hashlib.sha256(target.read_bytes()).hexdigest():
                raise ScriptError(f"untracked or modified output {filename}; use a fresh output directory")
    if destination.is_dir():
        for candidate in destination.iterdir():
            if not generated_name.fullmatch(candidate.name) or candidate.name in payloads:
                continue
            if not candidate.is_file() or candidate.resolve().parent != destination.resolve():
                raise ScriptError(f"unsafe stale chunk path: {candidate.name}")
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            if old_digests.get(candidate.name) != digest:
                raise ScriptError(f"untracked or modified stale chunk {candidate.name}; use a fresh output directory")
            if candidate.resolve() == source.resolve():
                raise ScriptError("source script is a stale output; use a fresh output directory")
            stale.append(candidate)
    destination.mkdir(parents=True, exist_ok=True)
    for filename, payload in payloads.items():
        (destination / filename).write_bytes(payload.encode("utf-8"))
    for filename in payloads:
        artifact = destination / filename
        if not artifact.is_file() or artifact.stat().st_size == 0:
            raise ScriptError(f"missing or empty emitted artifact: {filename}")
        if filename.endswith(".json"):
            json.loads(artifact.read_text(encoding="utf-8"))
        else:
            local_pages = re.findall(r"^(\d+)P$", artifact.read_text(encoding="utf-8"), re.M)
            if not 1 <= len(local_pages) <= 2 or local_pages != [str(n) for n in range(1, len(local_pages) + 1)]:
                raise ScriptError(f"invalid native page count or numbering: {filename}")
    for candidate in stale:
        candidate.unlink()
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description="Format a script into native Comicalizer batches of at most two pages")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cuts-per-page", type=int, default=4)
    args = parser.parse_args()
    try:
        index = format_script(args.input, args.output_dir, args.cuts_per_page)
    except (OSError, ValueError) as error:
        parser.exit(1, f"error: {error}\n")
    print(f"{len(index['batches'])} batch(es), {sum(len(batch['cut_ids']) for batch in index['batches'])} cuts -> {args.output_dir}")
    for warning in index["warnings"]:
        print("warning: " + warning)


if __name__ == "__main__":
    main()
