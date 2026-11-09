"""Optionally copy this repository's two workflow skills into .agents/skills.

The default/--check mode only reads files. --install copies the two known
SKILL.md files; it never edits user-global configuration or replaces conflicts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat
import sys


SKILL_NAMES = ("toon-production", "toon-recover")


def _is_link(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    # Windows junctions and other reparse points must not bypass symlink checks.
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _inside(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"path must stay inside the repository: {relative}")
    path = root
    for index, part in enumerate(relative.parts):
        path = path / part
        if _is_link(path):
            raise ValueError(f"symlinks/junctions are not allowed: {path}")
        if index < len(relative.parts) - 1 and path.exists() and not path.is_dir():
            raise ValueError(f"path component is not a directory: {path}")
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"path escapes the repository: {path}")
    return path


def bootstrap_skills(root: str | Path | None = None, *, install: bool = False) -> dict:
    """Preflight every file, then optionally create missing repo-local skills.

    root is a test/helper injection point. The CLI always uses its own repo,
    with no arbitrary source, destination, network, or user-global option.
    """
    root = Path(root) if root is not None else Path(__file__).absolute().parent.parent
    root = root.absolute()
    if _is_link(root):
        raise ValueError(f"repository root must not be a symlink/junction: {root}")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"repository root is not a directory: {root}")
    planned = []
    for name in SKILL_NAMES:
        source_relative = Path("docs/public/skills") / name / "SKILL.md"
        destination_relative = Path(".agents/skills") / name / "SKILL.md"
        source = _inside(root, source_relative)
        destination = _inside(root, destination_relative)
        if not source.is_file():
            raise ValueError(f"canonical skill source is missing: {source}")
        data = source.read_bytes()
        if not data:
            raise ValueError(f"canonical skill source is empty: {source}")
        if destination.exists():
            if not destination.is_file() or destination.read_bytes() != data:
                raise ValueError(f"conflicting skill destination; preserved without changes: {destination}")
            status = "identical"
        else:
            status = "missing"
        planned.append({"name": name, "source": source_relative.as_posix(),
                        "destination": destination_relative.as_posix(),
                        "sha256": hashlib.sha256(data).hexdigest(), "status": status,
                        "data": data})
    # No directory or file is created until every source and target has passed.
    if install:
        for item in planned:
            if item["status"] == "identical":
                continue
            relative = Path(item["destination"])
            for parent in reversed(relative.parents):
                if parent != Path("."):
                    _inside(root, parent).mkdir(exist_ok=True)
            destination = _inside(root, relative)
            # Exclusive creation also preserves a conflicting file that appeared
            # after preflight. Existing files are never truncated or replaced.
            with destination.open("xb") as stream:
                stream.write(item["data"])
            item["status"] = "installed"
    return {"mode": "install" if install else "check", "root": str(root),
            "status": "installed" if any(p["status"] == "installed" for p in planned) else
                      "already_current" if all(p["status"] == "identical" for p in planned) else "ready",
            "skills": [{key: value for key, value in item.items() if key != "data"} for item in planned]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="read-only source/destination status (default)")
    modes.add_argument("--install", action="store_true", help="copy only missing repo-local SKILL.md files")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(bootstrap_skills(install=args.install), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(f"Workflow skill bootstrap: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
