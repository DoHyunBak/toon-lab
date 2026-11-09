"""Explicit adoption of a reviewed production method; never retrospective legal clearance."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

from .factory import _load,_owned,_read,_save,_sha
from .generation_policy import validate_generation_job

VERSION='workflow-reviewed-v1'
RECORD='workflow_review.record.json'
REQUIRED_TEXT=('reviewer','rights_basis','license_conditions','permitted_external_processing','review_scope')


def _character_hash(job):
    return hashlib.sha256(json.dumps(job['characters'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def _evidence(record):
    if record.get('version')!=VERSION or record.get('legal_review_trigger')!='workflow_changes_or_rights_reports':
        raise ValueError('Unsupported reviewed production policy')
    for k in REQUIRED_TEXT:
        if not isinstance(record.get(k),str) or not record[k].strip():raise ValueError('Missing workflow rights/license review')
    if not isinstance(record.get('holds'),list) or any(not isinstance(s,str) or not s.strip() for s in record['holds']):
        raise ValueError('Workflow holds must be an explicit list')
    evidence=record.get('evidence')
    if not isinstance(evidence,list) or not evidence:raise ValueError('Workflow evidence is required')
    for item in evidence:
        path=Path(item['path'])
        if (not path.is_absolute() or path.is_symlink() or (path.suffix.lower() not in ('.md','.json','.txt') and path.name!='LICENSE')
                or any(part.lower().startswith('.env') or part=='_private' for part in path.parts)
                or not path.is_file() or path.stat().st_size>2*1024*1024 or _sha(path)!=item.get('sha256')):
            raise ValueError('Workflow evidence missing, changed or disallowed')


def adopt_workflow(job_dir,record_path):
    root,job=_load(job_dir)
    validate_generation_job(root,job)
    record=_read(record_path)
    _evidence(record)
    record={**record,'episode_sha256':_sha(_owned(root,job['episode'])),
            'characters_sha256':_character_hash(job),'legal_clearance':'not_issued',
            'prompt_sha256':{c['id']:_sha(_owned(root,c['prompt_file'])) for c in job['cuts']}}
    previous=_owned(root,RECORD)
    if previous.exists():
        history=root/'workflow_history';history.mkdir(exist_ok=True)
        archive=history/f'adoption_{len(list(history.glob("adoption_*.json")))+1:03d}.json'
        archive.write_bytes(previous.read_bytes())
    _save(previous,record)
    job['workflow_review']=RECORD
    job['workflow_review_sha256']=_sha(previous)
    _save(root/'job.json',job)
    return workflow_status(root,job)


def workflow_status(root,job):
    if not job.get('workflow_review'):return {'status':'not_adopted'}
    try:
        path=_owned(root,job['workflow_review'])
        if _sha(path)!=job.get('workflow_review_sha256'):raise ValueError('Workflow review changed')
        record=_read(path);_evidence(record)
        if (record['episode_sha256']!=_sha(_owned(root,job['episode']))
                or record['characters_sha256']!=_character_hash(job)
                or record['prompt_sha256']!={c['id']:_sha(_owned(root,c['prompt_file'])) for c in job['cuts']}):
            raise ValueError('Workflow inputs changed')
        return dict(status='held' if record['holds'] else 'reviewed',version=VERSION,
                    legal_review_trigger=record['legal_review_trigger'],holds=record['holds'],
                    legal_clearance='not_issued',evidence_count=len(record['evidence']))
    except (OSError,ValueError,KeyError,TypeError):
        return dict(status='stale',issue='Recheck actual inputs and evidence; adopt a new review record',legal_clearance='not_issued')
