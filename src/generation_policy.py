"""Text-only generation input contract; output images and QA are separate uses."""
from __future__ import annotations


MODE = "text_only"
POLICY_VERSION = "text-only-v1"
BRIEF_PREFIX = (f"Text-only generation policy {POLICY_VERSION}: use only this text; "
                "do not attach or reuse any images.")
IMAGE_FIELDS = {"image", "images", "atari", "background", "reference_images",
                "reference_ids", "references", "referenced_image_paths",
                "num_last_images_to_include", "assets"}


def validate_text_inputs(value):
    """Reject supported image mechanisms before opening source image files."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in IMAGE_FIELDS and item:
                raise ValueError("Text-only generation does not accept image inputs or reference IDs")
            validate_text_inputs(item)
    elif isinstance(value, list):
        for item in value:
            validate_text_inputs(item)


def validate_text_job(root, job):
    """Read-only validation; never convert a legacy job or rewrite its evidence."""
    from .factory import _owned, _read

    if (job.get("generation_input_mode") != MODE
            or job.get("generation_policy_version") != POLICY_VERSION):
        raise ValueError("Text-only generation requires a newly prepared text-only job; preserve legacy records")
    episode = _read(_owned(root, job["episode"]))
    validate_text_inputs(episode)
    validate_text_inputs(job.get("characters", {}))
    if [c["id"] for c in episode["cuts"]] != [c["id"] for c in job["cuts"]]:
        raise ValueError("Text-only generation episode/cut IDs changed; prepare a new job")
    for cut in job["cuts"]:
        if cut.get("reference_images") or cut.get("visual_reference_ids"):
            raise ValueError("Text-only generation cannot use image-reference job records")
        brief = _owned(root, cut["prompt_file"]).read_text(encoding="utf-8")
        if not brief.startswith(BRIEF_PREFIX + "\n"):
            raise ValueError("Text-only generation requires a fresh text-only brief")
    if job.get("reference_plan"):
        validate_text_inputs(_read(_owned(root, job["reference_plan"])))
    return episode


def validate_generation_job(root, job):
    """Dispatch only explicit fresh policies; never convert legacy/image history to text-only."""
    from .owned_episode_reference import MODE as OWN_MODE, validate_job
    if job.get('generation_input_mode') == OWN_MODE:
        return validate_job(root, job)
    return validate_text_job(root, job)
