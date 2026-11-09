"""Local production readiness checks; never start services or call image models."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
import tempfile


def check_runtime(*, project_root=None, reference_catalog=None) -> dict:
    """Check real local prerequisites and report actionable, independent failures."""
    root = Path(project_root or Path(__file__).resolve().parents[1]).resolve()
    catalog = Path(reference_catalog or "workspace/references/catalog.json")
    if not catalog.is_absolute():
        catalog = root / catalog
    checks = {}
    version = sys.version_info
    checks["python"] = {
        "status": "pass" if version >= (3, 11) else "blocked",
        "detail": f"Python {version.major}.{version.minor}.{version.micro}: {sys.executable}",
    }
    if checks["python"]["status"] == "blocked":
        checks["python"]["action"] = "Use Python 3.11 or newer; the pinned Pillow release requires it."

    try:
        pillow = importlib.import_module("PIL")
        Image = importlib.import_module("PIL.Image")
        ImageDraw = importlib.import_module("PIL.ImageDraw")
        checks["pillow"] = {"status": "pass", "detail": f"Pillow {pillow.__version__}"}
    except ImportError as error:
        checks["pillow"] = {"status": "blocked", "detail": str(error),
                            "action": "Run .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt."}
        Image = ImageDraw = None

    try:
        if Image is None:
            raise ValueError("Pillow is required to verify Korean glyphs.")
        from .bubble_renderer import _load_font
        text = "한글 검증"
        font = _load_font(None, 30, text)
        sample = Image.new("L", (240, 80), 0)
        ImageDraw.Draw(sample).text((4, 4), text, font=font, fill=255)
        if sample.getbbox() is None:
            raise ValueError("Korean sample rendered no pixels.")
        checks["korean_font"] = {"status": "pass", "detail": f"Verified Korean glyphs: {font.path}"}
    except (ImportError, OSError, ValueError) as error:
        checks["korean_font"] = {"status": "blocked", "detail": str(error),
                                 "action": "Run tools/setup_open_fonts.py to verify Pretendard and its OFL notice; "
                                           "WEBTOON_FONT must point to an approved font file."}

    try:
        if Image is None:
            raise ValueError("Pillow is required to verify reference originals.")
        if reference_catalog is None:
            checks["references"] = {"status": "pass", "detail": "Not requested for default text-only setup; no image library read."}
        else:
            checks["references"] = _check_references(catalog)
    except (ImportError, OSError, ValueError) as error:
        checks["references"] = {"status": "blocked", "detail": str(error),
                                "action": f"Restore the reference catalog and matching originals: {catalog}"}

    try:
        if Image is None:
            raise ValueError("Pillow is required to verify PNG writing.")
        with tempfile.TemporaryDirectory(prefix="factory-doctor-", dir=root / "workspace") as folder:
            sample = Path(folder) / "write-test.png"
            Image.new("RGB", (8, 8), "#ba9876").save(sample)
            with Image.open(sample) as reopened:
                reopened.verify()
            with Image.open(sample) as reopened:
                reopened.load()
                if reopened.size != (8, 8) or reopened.getpixel((0, 0)) != (186, 152, 118):
                    raise ValueError("Written PNG pixels differ after reopening.")
        checks["workspace"] = {"status": "pass", "detail": "Temporary PNG saved, reopened, verified and removed."}
    except (OSError, ValueError) as error:
        checks["workspace"] = {"status": "blocked", "detail": str(error),
                               "action": f"Ensure this existing workspace directory is writable: {root / 'workspace'}"}

    return {"status": "ready" if all(c["status"] == "pass" for c in checks.values()) else "blocked",
            "project_root": str(root), "reference_catalog": str(catalog.resolve()) if reference_catalog is not None else None,
            "checks": checks,
            "image_generation": {"provider": "imagegen", "executor": "assistant_tool",
                                 "availability": "not_locally_detectable",
                                 "detail": "Doctor checks the local Python assembly environment without network calls. "
                                           "Verify image generation and file saving through the agent's connected image tool."}}


def _check_references(catalog):
    """Only explicitly requested reference readiness may read the image library."""
    from .reference_guidance import load_references
    data = json.loads(catalog.read_text(encoding="utf-8-sig"))
    entries = data.get("references") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries or any(not isinstance(e, dict) for e in entries):
        raise ValueError("Reference catalog must contain at least one reference.")
    references = load_references(catalog, [entry.get("id") for entry in entries])
    return {"status": "pass", "detail": f"Verified {len(references)} reference originals, "
            "metadata, dimensions and SHA-256 hashes.", "count": len(references)}
