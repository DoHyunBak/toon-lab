"""Prepare imagegen briefs, import finished art, and letter/build a local episode.

Image generation is performed by the assistant's imagegen tool, never by this CLI.
Imported provider/prompt information is a declaration, not service-side proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from datetime import datetime, timezone

from PIL import Image, ImageOps

from .script_formatter import format_script, validate_episode
from .webtoon_stitcher import stitch_episode
from .reference_guidance import load_references, make_review, review_summary
from .generation_policy import (MODE, POLICY_VERSION, BRIEF_PREFIX,
                                validate_text_inputs, validate_generation_job)
from .owned_episode_reference import (MODE as OWN_MODE, POLICY_VERSION as OWN_POLICY_VERSION,
                                      BRIEF_PREFIX as OWN_BRIEF_PREFIX, validate_source as validate_owned_source,
                                      load_owned_references)


GENERATOR = "webtoon-factory-imagegen"
DEFAULT_REFERENCE_CATALOG = Path(__file__).resolve().parents[1] / "workspace/references/catalog.json"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _save(path, value):
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f"Refusing linked output: {path}")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".factory-", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _owned(root, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError(f"Unsafe job artifact path: {relative!r}")
    path = root / relative
    if not path.resolve().is_relative_to(root) or path.is_symlink():
        raise ValueError(f"Artifact escapes job directory: {relative}")
    return path


def _load(job_dir):
    root = Path(job_dir).resolve()
    job = _read(root / "job.json")
    if (not isinstance(job, dict) or job.get("generator") != GENERATOR
            or job.get("schema_version") != 1 or not isinstance(job.get("cuts"), list)
            or not job["cuts"]):
        raise ValueError("Invalid or unowned factory job.json")
    identifiers = [cut.get("id") for cut in job["cuts"]]
    _validate_ids(identifiers)
    _owned(root, job["episode"])
    return root, job


def _validate_ids(identifiers):
    seen = set()
    for identifier in identifiers:
        if (not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", identifier)
                or identifier.endswith(".") or re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]",
                                                           identifier.split(".")[0], re.I)
                or identifier.casefold() in seen):
            raise ValueError(f"Cut ID is not a unique portable filename: {identifier!r}")
        seen.add(identifier.casefold())


def _characters(path):
    if path is None:
        return {}
    source = Path(path).resolve()
    config = _read(source)
    entries = config.get("characters", config) if isinstance(config, dict) else None
    if not isinstance(entries, dict):
        raise ValueError("Characters must be an object, optionally inside 'characters'")
    validate_text_inputs(entries)
    result = {}
    for identifier, entry in entries.items():
        if not isinstance(entry, dict):
            raise ValueError(f"Invalid character entry: {identifier}")
        description = entry.get("description", entry.get("triggers", ""))
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"{identifier}: character description or triggers is required")
        references = entry.get("reference_images", [])
        if not isinstance(references, list):
            raise ValueError(f"{identifier}: reference_images must be a list")
        result[identifier] = {"display_name": entry.get("display_name", identifier),
                              "description": description, "reference_images": []}
    return result


def _reference_ids(value):
    if not isinstance(value, list) or any(not isinstance(item, str) or not re.fullmatch(r"ref_\d{4,}", item) for item in value):
        raise ValueError("reference_ids must be a list of library IDs such as ref_0001")
    return list(dict.fromkeys(value))


def _reference_health(root, job, reference_ids=None):
    if not job.get("reference_plan"):
        return {"status": "not_configured", "selected": [], "issues": []}
    try:
        plan = _read(_owned(root, job["reference_plan"]))
        saved = {ref["id"]: ref for cut in plan["cuts"] for ref in cut["references"]}
        if reference_ids is not None:
            saved = {identifier: saved[identifier] for identifier in reference_ids}
        if not saved:
            return {"status": "not_selected", "selected": [], "issues": []}
        current = load_references(plan["catalog"], list(saved))
        changed = [ref["id"] for ref in current if any(
            ref[key] != saved[ref["id"]][key] for key in ("sha256", "metadata_sha256"))]
        return {"status": "changed_since_prepare" if changed else "verified",
                "selected": list(saved), "issues": changed}
    except (OSError, ValueError, KeyError) as error:
        return {"status": "unavailable", "selected": [], "issues": [str(error)]}


def _reset_review(root, job):
    if not job.get("review_file"):
        return
    review = make_review(job["cuts"])
    for cut in job["cuts"]:
        if cut["imported"]:
            review["cuts"][cut["id"]]["image_sha256"] = cut["imported"]["sha256"]
    review["episode_sha256"] = _sha(_owned(root, job["episode"]))
    review["output_manifest_sha256"] = (job.get("output") or {}).get("sha256")
    _save(_owned(root, job["review_file"]), review)


def prepare_job(episode_path, job_dir, characters_path=None, *, reference_ids=None, reference_catalog=None):
    """Create a fresh job from user-authored TXT/JSON; preserve the original bytes."""
    source, root = Path(episode_path).resolve(), Path(job_dir).resolve()
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise FileExistsError("Job directory must be new or empty; prepare a separate job for revisions")
    source_data = _read(source) if source.suffix.lower() == '.json' else {}
    mode = source_data.get('generation_input_mode', MODE)
    if mode not in (MODE, OWN_MODE):
        raise ValueError('Prepare an explicit supported fresh generation mode; preserve legacy runs')
    owned = mode == OWN_MODE
    if reference_ids and not owned:
        raise ValueError("Text-only generation does not accept --reference")
    if owned:
        if reference_catalog is None:
            raise ValueError('Own-episode1 mode requires its explicit authorized reference catalog')
        validate_owned_source(source_data)
    elif source.suffix.lower() == ".json":
        validate_text_inputs(source_data)
    characters = _characters(characters_path)
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="factory-prepare-", dir=root.parent) as temporary:
        stage = Path(temporary)
        # Rebase guides to absolute paths before moving the staged job.
        chunks = stage / "conti"
        index = format_script(source, chunks)
        episode = _read(chunks / "episode.json")
        (validate_owned_source if owned else validate_text_inputs)(episode)
        _validate_ids([cut["id"] for cut in episode["cuts"]])
        used = {identifier for cut in episode["cuts"] for identifier in cut["characters"]}
        if used - characters.keys():
            raise ValueError("Supply --characters with identity descriptions for: " + ", ".join(sorted(used - characters.keys())))
        defaults = _reference_ids(reference_ids if reference_ids is not None else episode.get('reference_ids', [])) if owned else []
        episode["reference_ids"] = defaults
        catalog_path = Path(reference_catalog or DEFAULT_REFERENCE_CATALOG).resolve()
        by_cut = {cut["id"]: _reference_ids(cut.get('reference_ids', defaults)) if owned else [] for cut in episode["cuts"]}
        if owned and any(len(ids) != 1 for ids in by_cut.values()):
            raise ValueError('Each own-episode1 cut requires exactly one explicit reference')
        approved = {r['id']: r for r in load_owned_references(catalog_path,
                    list(dict.fromkeys(r for ids in by_cut.values() for r in ids)))} if owned else {}
        for cut in episode["cuts"]:
            cut["reference_ids"] = by_cut[cut["id"]]
        reference_plan = {"schema_version": 1, "catalog": str(catalog_path),
                          "catalog_sha256": _sha(catalog_path) if owned else None,
                          "usage": OWN_MODE if owned else "text_only_no_images", "cuts": []}
        # Re-format a rebased temporary manifest to preserve valid chunk artifact hashes.
        rebased = stage / "rebased.json"
        _save(rebased, episode)
        index = format_script(rebased, stage / "final_conti")
        (stage / "prompts").mkdir()
        (stage / "source").mkdir()
        shutil.copyfile(source, stage / "source" / source.name)
        records = []
        for cut in episode["cuts"]:
            references = [approved[r] for r in by_cut[cut['id']]] if owned else []
            focus = cut.get("reference_focus", episode.get("reference_focus", ""))
            if not isinstance(focus, str):
                raise ValueError("reference_focus must be a string explaining what to adapt")
            reference_plan["cuts"].append({"id": cut["id"], "reference_ids": by_cut[cut["id"]],
                                            "focus": focus, "references": references})
            camera = cut["camera"]
            frame_label = (f"Single webtoon panel: {cut['id']}" if cut.get('panel_count', 1) == 1 else
                           f"Intentional {cut['panel_count']}-panel webtoon strip render unit: {cut['id']}")
            lines = [OWN_BRIEF_PREFIX if owned else BRIEF_PREFIX, frame_label, f"Scene: {cut['description']}"]
            if owned:
                lines.extend(['Use the explicitly attached own-episode1 image for the approved rendering style; '
                              'current manuscript controls pose, action, props and setting. Do not copy a different reference event.',
                              'Reference use focus: ' + focus])
            if cut.get("prompt") and cut["prompt"] != cut["description"]:
                lines.append("Additional visual direction: " + cut["prompt"])
            lines.append("Camera: " + ", ".join(f"{key}={camera[key]}" for key in ("shot", "angle", "lens", "position")))
            lines.extend(f"Fixed character identity {identifier}: {characters[identifier]['description']}" for identifier in cut["characters"])
            lines.extend(["Preserve the supplied scene, identities, wardrobe and camera. Do not invent story events.",
                          "No lettering, text, speech balloons, captions, signatures, logos or watermarks.",
                          "Korean dialogue will be added locally after rendering. Keep the planned balloon regions uncluttered."])
            if cut["dialogue"]:
                lines.append("Planned lettering regions (do not draw balloons): " + json.dumps(
                    [{key: value for key, value in bubble.items() if key in {"box", "position", "tail"}}
                     for bubble in cut["dialogue"]], ensure_ascii=False))
            prompt_file = f"prompts/{cut['id']}.txt"
            (stage / prompt_file).write_text("\n".join(lines) + "\n", encoding="utf-8")
            records.append({"id": cut["id"], "prompt_file": prompt_file, "reference_images": references,
                            "reference_usage": OWN_MODE if owned else "text_only_no_images", "visual_reference_ids": by_cut[cut["id"]],
                            "reference_focus": focus, "imported": None, "history": []})
        job = {"generator": GENERATOR, "schema_version": 1, "job_id": root.name,
               "title": episode["title"], "episode": "conti/episode.json",
               "source": {"path": f"source/{source.name}", "original_path": str(source), "sha256": _sha(source)},
               "characters": characters, "cuts": records, "output": None,
               "reference_plan": "reference_plan.json", "review_file": "review.json",
               "approval": "not_reviewed", "generation": "assistant_imagegen_tool_required",
               "generation_input_mode": mode, "generation_policy_version": OWN_POLICY_VERSION if owned else POLICY_VERSION}
        root.mkdir(exist_ok=True)
        shutil.copytree(stage / "final_conti", root / "conti")
        # The final and staging conti directories have the same depth; their relative paths are valid.
        for name in ("source", "prompts"):
            shutil.copytree(stage / name, root / name)
        _save(root / "reference_plan.json", reference_plan)
        if owned:
            job['reference_plan_sha256'] = _sha(root/'reference_plan.json')
            job['reference_authorization_sha256'] = _read(catalog_path)['authorization']['sha256']
        _reset_review(root, job)
        _save(root / "job.json", job)
    return job


def import_cut(job_dir, cut_id, image_path, prompt_file=None, replace=False, *, provider="imagegen", used_reference_ids=None,
               generation_record=None):
    """Preserve source bytes and a lossless normalized PNG; retain previous versions."""
    root, job = _load(job_dir)
    validate_generation_job(root, job)
    owned = job['generation_input_mode'] == OWN_MODE
    if used_reference_ids and not owned:
        raise ValueError("Text-only generation cannot declare image references as used")
    if provider not in {"imagegen", "comfyui"}:
        raise ValueError("Unsupported generation provider")
    receipt = workflow = None
    if provider == "comfyui":
        if owned:
            raise ValueError("The existing own-reference catalog authorizes imagegen only; use a separately reviewed ComfyUI input route")
        if generation_record is None or prompt_file is None or used_reference_ids != []:
            raise ValueError("ComfyUI import requires --generation-record, actual --prompt-file and --no-visual-references")
        from .comfy_runner import validate_completed_output
        receipt, workflow = validate_completed_output(generation_record, image_path)
        # Only these audited core text-to-image nodes can enter a text_only job.
        # Arbitrary native graphs remain usable through the independent runner,
        # but a declaration alone cannot establish their image-input behavior.
        text_only_nodes = {"CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage",
                           "KSampler", "VAEDecode", "SaveImage", "LoraLoader"}
        graph = _read(workflow)
        if any(node.get("class_type") not in text_only_nodes for node in graph.values()):
            raise ValueError("ComfyUI text_only factory import accepts audited core text-to-image nodes only; unknown/image-input graphs need a separately reviewed route")
    elif generation_record is not None:
        raise ValueError("generation_record is only supported for provider=comfyui")
    record = next((cut for cut in job["cuts"] if cut["id"] == cut_id), None)
    if record is None:
        raise ValueError(f"Unknown cut ID: {cut_id}")
    if owned and (used_reference_ids != record['visual_reference_ids'] or prompt_file is None):
        raise ValueError('Own-episode1 import requires exact actual reference IDs and the actual prompt file')
    if record["imported"] and not replace:
        raise FileExistsError(f"{cut_id} is already imported; use --replace to retain a new version")
    if used_reference_ids is not None:
        used_reference_ids = _reference_ids(used_reference_ids)
        if set(used_reference_ids) - set(record.get("visual_reference_ids", [])):
            raise ValueError("Used visual references must have been selected for this cut at prepare")
        health = _reference_health(root, job, used_reference_ids)
        if used_reference_ids and health["status"] != "verified":
            raise ValueError("Selected reference sources changed/unavailable; prepare a fresh job before declaring their use")
    previous_review = None
    if job.get("review_file") and _owned(root, job["review_file"]).exists():
        previous_review = _read(_owned(root, job["review_file"]))["cuts"][cut_id]
    source = Path(image_path).resolve()
    with Image.open(source) as image:
        if getattr(image, "n_frames", 1) != 1:
            raise ValueError("Import a single still image, not animation/multiple frames")
        image.verify()
    with Image.open(source) as image:
        normalized = ImageOps.exif_transpose(image).convert("RGBA" if "A" in image.getbands() else "RGB")
        normalized.load()
    prompt = Path(prompt_file).read_text(encoding="utf-8-sig") if prompt_file else None
    if prompt is not None and not prompt.strip():
        raise ValueError("Provided actual generation prompt is empty")
    version = len(record["history"]) + (1 if record["imported"] else 0) + 1
    # Always version even the first file: IDs such as a_v002 remain distinct.
    stem = f"{cut_id}_v{version:03d}"
    relative = f"raw/{stem}.png"
    original_relative = f"raw/sources/{cut_id}_v{version:03d}{source.suffix or '.image'}"
    target, original = _owned(root, relative), _owned(root, original_relative)
    if target.exists() or original.exists():
        raise FileExistsError("Import destinations already exist; existing art is preserved")
    generation_evidence = None
    if receipt is not None:
        evidence = _owned(root, f"raw/generation/{stem}")
        evidence.mkdir(parents=True, exist_ok=False)
        saved_receipt, saved_workflow = evidence / "receipt.json", evidence / "workflow_api.json"
        shutil.copyfile(generation_record, saved_receipt)
        shutil.copyfile(workflow, saved_workflow)
        generation_evidence = {
            "receipt": {"path": saved_receipt.relative_to(root).as_posix(), "sha256": _sha(saved_receipt)},
            "workflow": {"path": saved_workflow.relative_to(root).as_posix(), "sha256": _sha(saved_workflow)},
            "prompt_id": receipt["prompt_id"],
            "verification": "local_receipt_and_bytes_bound_not_service_attested"}
    original.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, original)
    if receipt is not None and (_sha(original) != receipt["output"]["sha256"]
                                or _sha(saved_workflow) != receipt["workflow"]["sha256"]
                                or _read(saved_receipt) != receipt):
        raise ValueError("ComfyUI inputs changed during import; preserve evidence and retry in a fresh job")
    normalized.save(target, format="PNG")
    with Image.open(target) as saved:
        saved.verify()
    imported = {"image": relative, "sha256": _sha(target), "size": list(normalized.size),
                "original": original_relative, "source_path": str(source), "source_sha256": _sha(original),
                "provider": provider, "provider_verification": "declared", "reference_usage": "not_verified",
                "visual_reference_usage": {"status": "declared" if used_reference_ids is not None else "not_recorded",
                                           "ids": used_reference_ids},
                "prompt": prompt, "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest() if prompt else None,
                "prompt_verification": "provided" if prompt else "not_recorded",
                "imported_at": datetime.now(timezone.utc).isoformat(),
                "generation_input_mode": job['generation_input_mode'], "generation_policy_version": job['generation_policy_version']}
    if generation_evidence is not None:
        imported["generation_record"] = generation_evidence
    if record["imported"]:
        record["history"].append({**record["imported"], "visual_review": previous_review})
    record["imported"] = imported
    if job.get("output"):
        job["output_directory"] = str(Path(job["output"]["manifest"]).parent)
    job["output"] = None
    _reset_review(root, job)
    _save(root / "job.json", job)
    return imported


def job_status(job_dir):
    from .plagiarism import plagiarism_status
    from .legal_qa import legal_status
    root, job = _load(job_dir)
    imported, missing, changed = [], [], []
    for cut in job["cuts"]:
        item = cut["imported"]
        if not item:
            missing.append(cut["id"])
        elif not _owned(root, item["image"]).is_file() or _sha(_owned(root, item["image"])) != item["sha256"]:
            changed.append(cut["id"])
        else:
            imported.append(cut["id"])
    output_valid = False
    if job["output"]:
        try:
            output = Path(job["output"]["manifest"])
            emitted = _read(output)
            output_valid = (_sha(_owned(root, job["episode"])) == job["output"].get("episode_sha256")
                            and _sha(output) == job["output"]["sha256"]) and all(
                _sha(_owned(output.parent.resolve(), item["path"])) == item["sha256"]
                for item in [emitted["full"], *emitted["parts"]])
            # Optional local semantic assembly evidence belongs to this exact
            # build. Legacy jobs have no such fields and retain their behavior.
            binding = job["output"].get("assembly_input")
            if binding:
                output_valid = output_valid and _sha(_owned(root, binding["path"])) == binding["sha256"]
            output_valid = output_valid and all(
                _sha(_owned(output.parent.resolve(), item["path"])) == item["sha256"]
                for item in job["output"].get("assembly_files", []))
        except (OSError, ValueError, KeyError):
            pass
    expected_images = {cut["id"]: _sha(_owned(root, cut["imported"]["image"]))
                       if cut["imported"] and _owned(root, cut["imported"]["image"]).is_file() else None
                       for cut in job["cuts"]}
    expected_refs = {cut["id"]: cut.get("visual_reference_ids", []) for cut in job["cuts"]}
    try:
        review_path = _owned(root, job.get("review_file", "review.json"))
        review = review_summary(review_path, expected_images, expected_refs)
        if review_path.is_file():
            saved_review = _read(review_path)
            if (saved_review.get("episode_sha256") != _sha(_owned(root, job["episode"]))
                    or saved_review.get("output_manifest_sha256") != (job.get("output") or {}).get("sha256")):
                review["status"] = "stale"
                review["issues"].append("Episode or assembled output changed after review")
            elif review["status"] == "passed" and not output_valid:
                review["status"] = "not_reviewed"
                review["issues"].append("Lettered output must exist and be valid before final visual review")
    except (OSError, ValueError, KeyError) as error:
        review = {"status": "invalid", "issues": [str(error)]}
    return {"job_id": job["job_id"], "title": job["title"], "cut_count": len(job["cuts"]),
            "generation_input_mode": job.get("generation_input_mode", "legacy_unverified"),
            "generation_policy_version": job.get("generation_policy_version"),
            "imported": imported, "missing": missing, "changed": changed,
            "status": "needs_images" if missing or changed else "built" if output_valid else "ready_to_build",
            "output": job["output"], "output_valid": output_valid,
            "visual_references": _reference_health(root, job), "reference_review": review,
            "plagiarism_review": plagiarism_status(root, job),
            "legal_qa": {stage: legal_status(root, job, stage=stage) for stage in ("preflight", "final")},
            "visual_reference_usage": {cut["id"]: (cut["imported"] or {}).get("visual_reference_usage", {"status": "not_recorded", "ids": None})
                                       for cut in job["cuts"]}, "approval": "not_reviewed"}


def build_job(job_dir, output_dir=None, *, overwrite=False, **stitch_options):
    root, job = _load(job_dir)
    status = job_status(root)
    if status["missing"] or status["changed"]:
        raise ValueError("Missing or changed imported art: " + ", ".join(status["missing"] + status["changed"]))
    episode = validate_episode(_read(_owned(root, job["episode"])))
    if [cut["id"] for cut in episode["cuts"]] != [cut["id"] for cut in job["cuts"]]:
        raise ValueError("Episode cut IDs/order changed; prepare a new job")
    for cut, record in zip(episode["cuts"], job["cuts"]):
        cut["image"] = str(_owned(root, record["imported"]["image"]))
    manifest = root / "episode.imported.json"
    if manifest.exists() and _sha(manifest) != job.get("build_manifest", {}).get("sha256"):
        raise ValueError("Unowned or modified episode.imported.json; preserve it and choose a fresh job")
    _save(manifest, episode)
    job["build_manifest"] = {"path": manifest.name, "sha256": _sha(manifest)}
    _save(root / "job.json", job)
    destination = Path(output_dir or job.get("output_directory") or root / "output").resolve()
    result = stitch_episode(manifest, destination, overwrite=overwrite, **stitch_options)
    job["output"] = {"manifest": str(result), "sha256": _sha(result),
                     "episode_sha256": _sha(_owned(root, job["episode"])), "approval": "not_reviewed"}
    job["output_directory"] = str(destination)
    if job.get("review_file"):
        review_path = _owned(root, job["review_file"])
        old_review = _read(review_path) if review_path.exists() else {}
        if (old_review.get("episode_sha256") != job["output"]["episode_sha256"]
                or old_review.get("output_manifest_sha256") != job["output"]["sha256"]):
            _reset_review(root, job)
    _save(root / "job.json", job)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="런타임·한글 폰트·참고 자료·쓰기 상태 확인")
    doctor.add_argument("--reference-catalog", type=Path, help="optional read-only QA/library audit; not a generation input")
    next_parser = commands.add_parser("next", help="다음 구동 작업과 imagegen 입력 반환")
    next_parser.add_argument("job", type=Path)
    next_parser.add_argument("--cut", help="특정 컷 생성/재생성 입력 반환")
    prepare = commands.add_parser("prepare", help="사용자 원고 → 2쪽 청크 + 컷별 생성 브리프")
    prepare.add_argument("episode", type=Path)
    prepare.add_argument("--output-dir", type=Path, required=True)
    prepare.add_argument("--characters", type=Path)
    prepare.add_argument("--reference", action="append", help="explicit owned-episode1 ID; text-only rejects it, owned mode requires one per cut")
    prepare.add_argument("--reference-catalog", type=Path, help="explicit authorized catalog required for own-episode1 mode")
    importer = commands.add_parser("import", help="완성 이미지 보존·등록 (이미지 생성 기능 아님)")
    importer.add_argument("job", type=Path)
    importer.add_argument("cut_id")
    importer.add_argument("image", type=Path)
    importer.add_argument("--prompt-file", type=Path)
    importer.add_argument("--provider", choices=["imagegen", "comfyui"], default="imagegen")
    importer.add_argument("--generation-record", type=Path, help="completed ComfyUI runner receipt bound to exact source bytes")
    importer.add_argument("--replace", action="store_true")
    usage = importer.add_mutually_exclusive_group()
    usage.add_argument("--used-reference", action="append", help="actually supplied visual reference ID (operator declaration)")
    usage.add_argument("--no-visual-references", action="store_true", help="declare that no visual examples were supplied")
    build = commands.add_parser("build", help="한국어 식자 + 800px 세로 조립")
    build.add_argument("job", type=Path)
    build.add_argument("--output-dir", type=Path)
    build.add_argument("--overwrite", action="store_true")
    build.add_argument("--font", type=Path)
    build.add_argument("--font-size", type=int, default=30)
    build.add_argument("--min-font-size", type=int, default=16)
    build.add_argument("--padding", type=int, default=120)
    build.add_argument("--max-height", type=int, default=4000)
    status = commands.add_parser("status", help="컷별 등록 현황과 누락 확인")
    status.add_argument("job", type=Path)
    review = commands.add_parser("review", help="예시 기반 7항목 검수 현황 확인 (읽기 전용)")
    review.add_argument("job", type=Path)
    review.add_argument("--report", type=Path, help="현재 이미지·원고·출력에 맞는 관찰 검수 보고서 제출")
    plagiarism = commands.add_parser("plagiarism", help="명시된 비교군으로 Jev 표현 유사성 검사 (외부 API 전송)")
    plagiarism.add_argument("job", type=Path)
    plagiarism.add_argument("--corpus", type=Path, required=True, help="외부 처리 권한·검사 범위를 기록한 비교군 JSON")
    plagiarism.add_argument("--max-requests", type=int, default=25, help="이번 실행의 최대 API 요청 수; 다시 실행하면 이어서 검사")
    plagiarism_review = commands.add_parser("plagiarism-review", help="현재 Jev 결과와 실제 비교 이미지의 관찰 검수 제출")
    plagiarism_review.add_argument("job", type=Path)
    plagiarism_review.add_argument("--report", type=Path, required=True)
    legal = commands.add_parser("legal-check", help="인덱싱한 법률·최소 사실 근거의 Jev 법률 위험 QA (외부 API 전송)")
    legal.add_argument("job", type=Path)
    legal.add_argument("--index", type=Path, required=True, help="현행 조문·이용행위·전송 허용 근거를 연결한 JSON")
    legal.add_argument("--stage", choices=("preflight", "final"), default="preflight")
    legal.add_argument("--max-requests", type=int, default=25)
    legal_review = commands.add_parser("legal-review", help="현재 법률 QA의 행위별 근거 검토 제출; 법률 인증 아님")
    legal_review.add_argument("job", type=Path)
    legal_review.add_argument("--report", type=Path, required=True)
    legal_review.add_argument("--stage", choices=("preflight", "final"), default="preflight")
    workflow = commands.add_parser("adopt-workflow", help="실제 입력 권한·라이선스 근거를 검토 공정에 연결; 법적 인증 아님")
    workflow.add_argument("job", type=Path)
    workflow.add_argument("--record",type=Path,required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            from .runtime_check import check_runtime
            result = check_runtime(reference_catalog=args.reference_catalog)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "ready" else 1
        elif args.command == "next":
            from .operations import next_action
            print(json.dumps(next_action(args.job, args.cut), ensure_ascii=False, indent=2))
        elif args.command == "prepare":
            result = prepare_job(args.episode, args.output_dir, args.characters,
                                 reference_ids=args.reference, reference_catalog=args.reference_catalog)
            print(f"{result['title']}: {len(result['cuts'])}컷 준비 → {args.output_dir}")
            print("에이전트의 이미지 생성 도구로 원화를 만든 후 import 합니다. 다음 단계는 next로 확인하세요.")
        elif args.command == "import":
            result = import_cut(args.job, args.cut_id, args.image, args.prompt_file, args.replace, provider=args.provider,
                                used_reference_ids=[] if args.no_visual_references else args.used_reference,
                                generation_record=args.generation_record)
            print(f"{args.cut_id}: 등록 {result['size'][0]}×{result['size'][1]} → {result['image']}")
        elif args.command == "build":
            print(build_job(args.job, args.output_dir, overwrite=args.overwrite, font_path=args.font,
                            font_size=args.font_size, min_font_size=args.min_font_size,
                            padding=args.padding, max_height=args.max_height))
        elif args.command == "review":
            if args.report:
                from .operations import submit_review
                result = submit_review(args.job, args.report)
            else:
                result = job_status(args.job)["reference_review"]
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "plagiarism":
            from .plagiarism import run_check
            result = run_check(args.job, args.corpus, max_requests=args.max_requests)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1 if result["status"] in ("error", "stale", "not_checked") else 0
        elif args.command == "plagiarism-review":
            from .plagiarism import submit_plagiarism_review
            print(json.dumps(submit_plagiarism_review(args.job, args.report), ensure_ascii=False, indent=2))
        elif args.command == "adopt-workflow":
            from .workflow_policy import adopt_workflow
            print(json.dumps(adopt_workflow(args.job,args.record),ensure_ascii=False,indent=2))
        elif args.command == "legal-check":
            from .legal_qa import run_legal_check
            result = run_legal_check(args.job, args.index, stage=args.stage, max_requests=args.max_requests)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] in ("screened", "passed") else 1
        elif args.command == "legal-review":
            from .legal_qa import submit_legal_review
            result = submit_legal_review(args.job, args.report, stage=args.stage)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "passed" else 1
        else:
            print(json.dumps(job_status(args.job), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, f"factory failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
