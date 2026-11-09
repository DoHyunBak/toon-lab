"""Bind an existing factory job to semantic assembly and a fresh visual review.

python tools/build_layout_job.py JOB INPUT.json --output-dir NEW --font FONT
Only current imported raw files, current dialogue and exact scene order may be
assembled. This does not submit visual QA or grant human/publication approval.
"""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.factory import _load,_owned,_read,_save,_sha,_reset_review,job_status
from src.generation_policy import validate_generation_job
from src.workflow_policy import workflow_status
from tools.apply_layout_policy import run


def build_layout_job(job_dir,layout_input,output_dir,font=None):
    root,job=_load(job_dir);validate_generation_job(root,job)
    if workflow_status(root,job)['status']!='reviewed':raise ValueError('Adopt the current reviewed workflow first')
    status=job_status(root)
    if status['missing'] or status['changed']:raise ValueError('All current raw imports must be intact before layout')
    episode_path=_owned(root,job['episode']);episode_digest=_sha(episode_path)
    episode=_read(episode_path);source=Path(layout_input).resolve();data=_read(source)
    expected=[c['id'] for c in job['cuts']]
    if data.get('expected_ids')!=expected or [p['id'] for p in data['panels']]!=expected:
        raise ValueError('Layout must preserve all current scene IDs and order')
    if [c['id'] for c in episode['cuts']]!=expected:raise ValueError('Current manuscript order changed')
    for p,c,record in zip(data['panels'],episode['cuts'],job['cuts']):
        raw=_owned(root,record['imported']['image'])
        if (source.parent/p['source_image']).resolve()!=raw:raise ValueError('Layout source must be the current imported raw: '+c['id'])
        if p.get('dialogue',[])!=c.get('dialogue',[]) or p.get('description','')!=c.get('description',''):
            raise ValueError('Layout dialogue/description differs from current manuscript: '+c['id'])
    destination=Path(output_dir).resolve()
    if destination.exists():raise FileExistsError('Preserve previous assembly; choose a fresh directory')
    if not source.is_relative_to(ROOT) or not destination.is_relative_to(ROOT):raise ValueError('Keep assembly in this project')
    # Immutable per-build snapshot; generation inputs and old review stay intact.
    history=root/'layout_inputs';history.mkdir(exist_ok=True)
    version=1
    while (history/f'v{version:03d}').exists():version+=1
    snapshot=history/f'v{version:03d}';snapshot.mkdir()
    for p in data['panels']:p['source_image']=str((source.parent/p['source_image']).resolve())
    frozen=snapshot/'input.json';_save(frozen,data);frozen_digest=_sha(frozen)
    _save(snapshot/'origin.json',dict(path=str(source),sha256=_sha(source),source_episode_sha256=_sha(_owned(root,job['episode']))))
    run(frozen,destination,font)
    if _sha(episode_path)!=episode_digest or _sha(frozen)!=frozen_digest:
        raise ValueError('Assembly inputs changed during rendering; do not bind this output')
    if any(_sha(_owned(root,c['imported']['image']))!=c['imported']['sha256'] for c in job['cuts']):
        raise ValueError('Raw art changed during rendering; do not bind this output')
    manifest=destination/'manifest.json'
    job['output']=dict(manifest=str(manifest),sha256=_sha(manifest),episode_sha256=episode_digest,approval='not_reviewed',
        assembly_input=dict(path=frozen.relative_to(root).as_posix(),sha256=_sha(frozen)),
        assembly_files=[dict(path=name,sha256=_sha(destination/name)) for name in ['episode.json','layout_plan.json','layout_provenance.json','input_contract.json']],
        assembly_mode='semantic_layout_with_measured_lettering')
    job['output_directory']=str(destination)
    _reset_review(root,job);_save(root/'job.json',job)
    return manifest


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('job',type=Path);ap.add_argument('layout_input',type=Path)
    ap.add_argument('--output-dir',type=Path,required=True);ap.add_argument('--font',type=Path);a=ap.parse_args()
    print(json.dumps(dict(manifest=str(build_layout_job(a.job,a.layout_input,a.output_dir,a.font)),visual_review='not_reviewed')))
if __name__=='__main__':main()
