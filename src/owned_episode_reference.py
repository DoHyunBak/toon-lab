"""Explicitly authorized own-episode1 inputs; operator records are not legal certification."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from .reference_guidance import load_references, _inside

MODE = 'authorized_own_episode1_reference'
POLICY_VERSION = 'own-episode1-reference-v1'
BRIEF_PREFIX = ('Authorized own-episode1 reference policy ' + POLICY_VERSION +
                ': use only the explicitly listed permission-reviewed episode1 images and current manuscript text; '
                'never use other conversation images or third-party captures.')


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_source(episode):
    """Only explicit reference_ids become additional inputs; all other image mechanisms stay excluded."""
    from .generation_policy import validate_text_inputs
    if episode.get('generation_input_mode') != MODE:
        raise ValueError('Own-episode1 mode must be explicit in a fresh source')
    text = copy.deepcopy(episode)
    text.pop('reference_ids', None)
    for cut in text.get('cuts', []):
        cut.pop('reference_ids', None)
    validate_text_inputs(text)


def load_owned_references(catalog_path, identifiers):
    """Check selected bytes, origin bounds and frozen user-authorization/benchmark records."""
    catalog_path = Path(catalog_path).resolve()
    catalog = _read(catalog_path)
    if catalog.get('usage_mode') != MODE:
        raise ValueError('This is not an authorized own-episode1 catalog')
    record = catalog.get('authorization', {})
    auth_path = _inside(catalog_path.parent, record.get('path'))
    if _sha(auth_path) != record.get('sha256'):
        raise ValueError('Reference authorization changed')
    auth = _read(auth_path)
    if (auth.get('scope') != 'own_episode1_outputs_only' or auth.get('user_authorized') is not True
            or auth.get('source_episode_id') != 'ep001' or auth.get('holds') != []
            or 'imagegen_reference' not in auth.get('permitted_actions', [])):
        raise ValueError('Own-episode1 reference permission absent or held')
    source_root = Path(auth['source_root'])
    if not source_root.is_absolute() or source_root.is_symlink() or not source_root.is_dir():
        raise ValueError('Authorized source root unavailable')
    benchmark = auth.get('style_benchmark', {})
    bp = Path(benchmark['path'])
    if (not bp.is_absolute() or bp.suffix.lower() != '.json' or bp.is_symlink()
            or _sha(bp) != benchmark.get('sha256') or _read(bp).get('approval') != 'approved'):
        raise ValueError('Style benchmark authorization missing or changed')
    refs = load_references(catalog_path, identifiers)
    for ref in refs:
        metadata = _read(ref['metadata_path'])
        origin = metadata.get('owned_source', {})
        source = Path(origin.get('path', ''))
        if (origin.get('episode_id') != 'ep001' or origin.get('holds') != []
                or origin.get('review_status') != 'reviewed_for_internal_reference_use'
                or 'imagegen_reference' not in origin.get('permitted_actions', [])
                or not source.is_absolute() or source.is_symlink()
                or not source.resolve().is_relative_to(source_root.resolve())
                or not source.is_file() or _sha(source) != ref['sha256']
                or origin.get('sha256') != ref['sha256']):
            raise ValueError('Selected reference origin/permission changed or outside own episode1 scope')
    return refs


def validate_job(root, job):
    from .factory import _owned
    from .generation_policy import validate_text_inputs
    if job.get('generation_policy_version') != POLICY_VERSION:
        raise ValueError('Own-episode1 policy version mismatch; preserve old runs')
    episode = _read(_owned(root, job['episode']))
    validate_source(episode)
    validate_text_inputs(job['characters'])
    if [c['id'] for c in episode['cuts']] != [c['id'] for c in job['cuts']]:
        raise ValueError('Episode IDs changed; prepare a fresh job')
    plan_path = _owned(root, job['reference_plan'])
    if _sha(plan_path) != job.get('reference_plan_sha256'):
        raise ValueError('Owned reference plan changed')
    plan = _read(plan_path)
    catalog = _read(plan['catalog'])
    if catalog.get('authorization', {}).get('sha256') != job.get('reference_authorization_sha256'):
        raise ValueError('Owned reference authorization no longer matches prepared job')
    selected = list(dict.fromkeys(r for c in job['cuts'] for r in c.get('visual_reference_ids', [])))
    current = {r['id']: r for r in load_owned_references(plan['catalog'], selected)}
    if [c['id'] for c in plan['cuts']] != [c['id'] for c in job['cuts']]:
        raise ValueError('Reference plan cut order changed')
    for cut, source, planned in zip(job['cuts'], episode['cuts'], plan['cuts']):
        ids = cut.get('visual_reference_ids')
        if (not isinstance(ids, list) or len(ids) != 1 or ids != source.get('reference_ids')
                or ids != planned.get('reference_ids')):
            raise ValueError('Each owned-reference cut needs exactly one explicit approved input')
        expected = current[ids[0]]
        for refs in (cut.get('reference_images'), planned.get('references')):
            if (not isinstance(refs, list) or len(refs) != 1 or any(
                    refs[0].get(k) != expected.get(k) for k in ('id', 'path', 'sha256', 'metadata_sha256'))):
                raise ValueError('Selected owned-reference snapshot changed')
        if not _owned(root, cut['prompt_file']).read_text(encoding='utf-8').startswith(BRIEF_PREFIX + '\n'):
            raise ValueError('Own-reference job needs an explicit own-reference brief')
        imported = cut.get('imported')
        if imported and (imported.get('generation_input_mode') != MODE
                         or imported.get('visual_reference_usage', {}).get('status') != 'declared'
                         or imported['visual_reference_usage'].get('ids') != ids):
            raise ValueError('Actual reference use missing or different; preserve and repair provenance')
    return episode
