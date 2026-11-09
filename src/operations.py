"""Agent handoff actions and validated review submission for the local factory."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from .factory import _load, _owned, _read, _save, _sha, job_status
from .plagiarism import plagiarism_status
from .reference_guidance import review_summary
from .generation_policy import MODE, POLICY_VERSION, validate_generation_job
from .owned_episode_reference import MODE as OWN_MODE
from .workflow_policy import workflow_status
from .production_control import bound_context, pending_replan, sequence_defects


def _generation(root, job, cut_id):
    record = next((cut for cut in job["cuts"] if cut["id"] == cut_id), None)
    if record is None:
        raise ValueError(f"Unknown cut: {cut_id}")
    defects = sequence_defects(root, job, cut_id)
    if defects:
        return {'action': 'resolve_sequence_defect', 'cut_id': cut_id, 'defects': defects,
                'instruction': 'Fix the shared cause; validate one changed scene before expanding this sequence.'}
    source_episode = validate_generation_job(root, job)
    cut = next(c for c in source_episode["cuts"] if c["id"] == cut_id)
    brief = _owned(root, record["prompt_file"]).read_text(encoding="utf-8")
    if pending_replan(root, cut_id, brief):
        return {'action':'replan', 'cut_id':cut_id,
                'instruction':'Revise the method and bind a replan resolution to the changed prompt before generation.'}
    context = bound_context(root, job, cut_id)
    if context:
        brief = brief + '\n' + context
    render_size = cut.get("render_size", [1024, 1536])
    if (not isinstance(render_size, list) or len(render_size) != 2
            or any(type(n) is not int or not 256 <= n <= 4096 for n in render_size)):
        raise ValueError("render_size must contain two integers from 256 to 4096")
    panel_count = cut.get("panel_count", 1)
    if type(panel_count) is not int or not 1 <= panel_count <= 8:
        raise ValueError("panel_count must be an integer from 1 to 8")
    format_line = (f"Generate ONE finished vertical Korean color webtoon STRIP with exactly {panel_count} sequential panels, "
                   f"{render_size[0]} x {render_size[1]} pixels. Follow the text-defined panel plan; preserve its reading order and gutters."
                   if panel_count > 1 else
                   f"Generate ONE finished {'landscape' if render_size[0] > render_size[1] else 'portrait'} Korean color webtoon panel, {render_size[0]} x {render_size[1]} pixels, edge-to-edge artwork.")
    owned = job['generation_input_mode'] == OWN_MODE
    prompt = "\n".join([
        format_line,
        "Use case: illustration-story. Render only the approved current scene. No text, speech balloons, captions, watermark" + (" or page collage." if panel_count == 1 else f". The {panel_count}-panel strip is intentional; do not add extra panels."),
        ("Use ONLY the explicitly listed authorized own-episode1 reference image. Never use other conversation images, "
         "third-party captures, unrelated character sheets or unlisted previous generated cuts." if owned else
         "Use text prompts only. Do not attach or reuse any images, character sheets, previous cuts or conversation images."),
        "Follow the approved character identities and current manuscript. Keep the planned lettering area calm.",
        brief,
    ])
    imagegen = {'prompt': prompt, 'transparent_background': False}
    if owned:
        imagegen['referenced_image_paths'] = [r['path'] for r in record['reference_images']]
    return {"action": "generate", "cut_id": cut_id, "replace": bool(record["imported"]),
            "generation_input_mode": job['generation_input_mode'], "generation_policy_version": job['generation_policy_version'],
            "imagegen": imagegen, "used_reference_ids": record['visual_reference_ids'] if owned else [],
            "instruction": ('Call built-in imagegen with exactly this prompt and the one listed own-episode1 path; '
                            'omit num_last_images_to_include. Save the EXACT prompt and declare the listed actual --used-reference ID on import.' if owned else
                            "Use the agent's available image-generation tool with this text-only prompt and no image inputs. Save the actual tool, prompt and image locally; import with --provider imagegen --prompt-file FILE --no-visual-references.")}


def _provenance(job, root):
    missing = []
    for cut in job["cuts"]:
        item = cut["imported"]
        if item.get("prompt_verification") != "provided" or not item.get("prompt"):
            missing.append(f"{cut['id']}: actual generation prompt not recorded")
        elif _sha_text(item["prompt"]) != item.get("prompt_sha256"):
            missing.append(f"{cut['id']}: actual generation prompt hash differs")
        if item.get("visual_reference_usage", {}).get("status") != "declared":
            missing.append(f"{cut['id']}: actual visual-reference use or explicit non-use not recorded")
        try:
            if _sha(_owned(root, item["original"])) != item["source_sha256"]:
                missing.append(f"{cut['id']}: preserved original hash differs")
        except (OSError, ValueError, KeyError):
            missing.append(f"{cut['id']}: preserved original missing")
        if item.get("provider") != "imagegen":
            missing.append(f"{cut['id']}: unsupported generation provider; preserve the original job and use a supported import route")
    return missing


def _sha_text(value):
    import hashlib
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _legal_action(root, status, stage):
    screening = status["legal_qa"][stage]
    if screening.get("status") == "passed":
        return None
    review = screening.get("status") == "screened"
    command = (f'.\\factory.ps1 legal-review "{root}" --stage {stage} --report FILE' if review else
               f'.\\factory.ps1 legal-check "{root}" --stage {stage} --index FILE')
    return {"action": "legal_review" if review else "legal_check", "stage": stage,
            "job": str(root), "legal_qa": screening, "command": command,
            "instruction": "Research current applicable law before work; index official articles, dates, action-specific facts and lawful evidence. Send only explicitly authorized minimal facts to Jev, then review every action. Resolve risk, uncertainty or missing evidence before rerunning; no manual override or legal certification."}


def next_action(job_dir, cut_id=None):
    """Read the job and return the next executable assistant action; never generate art."""
    root, job = _load(job_dir)
    validate_generation_job(root, job)
    status = job_status(root)
    if status["changed"]:
        return {"action": "repair_inputs", "issues": status["changed"]}
    workflow=workflow_status(root,job)
    if workflow['status'] in {'held','stale'}:
        return {'action':'resolve_workflow_review','workflow_review':workflow}
    reviewed_workflow=workflow['status']=='reviewed'
    if job['generation_input_mode'] == OWN_MODE and not reviewed_workflow:
        return {'action':'adopt_workflow','generation_input_mode':OWN_MODE,
                'instruction':'Connect the actual own-episode1 permissions, license conditions and workflow-change evidence with adopt-workflow before generation.'}
    if not reviewed_workflow:
        legal = _legal_action(root, status, "preflight")
        if legal:
            return legal
    if cut_id is not None:
        return _generation(root, job, cut_id)
    if status["missing"]:
        return _generation(root, job, status["missing"][0])
    defects = sequence_defects(root, job)
    if defects:
        return {'action': 'resolve_sequence_defect', 'defects': defects}
    issues = _provenance(job, root)
    if issues:
        return {"action": "record_provenance", "issues": issues,
                "instruction": "Preserve the history; re-import with --replace, the actual prompt and actual --used-reference IDs or --no-visual-references."}
    if not status["output_valid"]:
        destination = Path(job.get("output_directory") or root / "output")
        return {"action": "build", "job": str(root), "output_dir": str(destination),
                "overwrite": (destination / "manifest.json").exists()}
    review_status = status["reference_review"]["status"]
    if review_status == "needs_fix":
        return {"action": "fix_review", "review": str(_owned(root, job["review_file"])),
                "instruction": "Fix the recorded issue using the smallest change: lettering/layout first where appropriate; use next --cut ID when new artwork is required."}
    if review_status != "passed":
        return {"action": "review", "review_template": str(_owned(root, job.get("review_file", "review.json"))),
                "raw_images": [str(_owned(root, c["imported"]["image"])) for c in job["cuts"]],
                "output_manifest": status["output"]["manifest"],
                "instruction": "Inspect raw art and lettered output at full and mobile scale; fill a COPY of the current review template with observed notes, then review --report FILE. Do not edit its bound hashes."}
    screening = plagiarism_status(root, job)
    if reviewed_workflow:
        return {'action':'ready','output_manifest':status['output']['manifest'],
                'cut_count':len(job['cuts']),'technical_output_valid':True,
                'agent_visual_review':'passed','generation_input_mode':job['generation_input_mode'],
                'generation_policy_version':job['generation_policy_version'],'workflow_review':workflow,
                'routine_jev_required':False,'actual_similarity_screening':screening,
                'actual_legal_screenings':status['legal_qa'],'legal_clearance':'not_issued',
                'editorial_approval':'not_reviewed','publication_approval':'not_granted'}
    if screening.get("status") != "passed":
        needs_review = screening.get("status") in {"screened", "needs_human_review"}
        command = (f'.\\factory.ps1 plagiarism-review "{root}" --report FILE' if needs_review else
                   f'.\\factory.ps1 plagiarism "{root}" --corpus FILE')
        return {"action": "plagiarism_review" if needs_review else "plagiarism_check", "job": str(root),
                "plagiarism_review": screening, "command": command,
                "instruction": "Screen only the explicitly authorized comparison corpus; this does not establish internet-wide originality or legal clearance. Inspect the current findings and submit a separate human review before ready."}
    legal = _legal_action(root, status, "final")
    if legal:
        return legal
    return {"action": "ready", "output_manifest": status["output"]["manifest"],
            "cut_count": len(job["cuts"]), "technical_output_valid": True,
            "agent_visual_review": "passed", "plagiarism_review": "passed",
            "generation_input_mode": MODE, "generation_policy_version": POLICY_VERSION,
            "legal_qa": {"preflight": "passed", "final": "passed", "legal_clearance": "not_issued"},
            "editorial_approval": "not_reviewed"}


def submit_review(job_dir, report_path):
    """Record an observed review only if it matches the current art/script/output."""
    root, job = _load(job_dir)
    if not job.get("review_file"):
        raise ValueError("Legacy job has no review template; prepare a new job for the current workflow")
    status = job_status(root)
    if not status["output_valid"] or status["missing"] or status["changed"]:
        raise ValueError("Build a valid current output before submitting a review")
    report_path = Path(report_path)
    report = _read(report_path)
    if (report.get("episode_sha256") != _sha(_owned(root, job["episode"]))
            or report.get("output_manifest_sha256") != status["output"]["sha256"]):
        raise ValueError("Review report is stale: episode/output hashes do not match")
    images = {c["id"]: c["imported"]["sha256"] for c in job["cuts"]}
    references = {c["id"]: c.get("visual_reference_ids", []) for c in job["cuts"]}
    summary = review_summary(report_path, images, references)
    if summary["status"] == "stale":
        raise ValueError("Review report is stale: image/reference IDs differ")
    _save(_owned(root, job["review_file"]), report)
    return summary
