"""Deterministic production controls; no model, network, or quality approvals."""
import hashlib
import json

CORRECTION = '\nCURRENT SCENE CORRECTION:\n'


def replace_correction(brief, correction):
    """History belongs in attempt records, never in competing live directives."""
    if not correction.strip():
        raise ValueError('A concrete correction is required')
    return brief.split(CORRECTION, 1)[0].rstrip() + CORRECTION + correction.strip() + '\n'


def compile_context(episode_bytes, context):
    episode = json.loads(episode_bytes)
    if context.get('episode_sha256') != hashlib.sha256(episode_bytes).hexdigest():
        raise ValueError('Scene context is stale')
    ids = [c['id'] for c in episode['cuts']]
    states = context.get('scenes', [])
    if [s.get('id') for s in states] != ids or len(set(ids)) != len(ids):
        raise ValueError('Context must cover every scene exactly once in source order')
    shared = context.get('shared', {})
    for field in ('setting', 'visual_invariants'):
        if not isinstance(shared.get(field), str) or not shared[field].strip():
            raise ValueError('Missing shared ' + field)
    result = {}
    prior_states = {}
    for source, state in zip(episode['cuts'], states):
        if state.get('source_action') != source['description']:
            raise ValueError('Source action differs: ' + source['id'])
        for field in ('staging', 'prop_state', 'protected_subjects'):
            if not isinstance(state.get(field), str) or not state[field].strip():
                raise ValueError('Missing ' + field + ': ' + source['id'])
        result[source['id']] = '\n'.join([
            'CURRENT SOURCE-BOUND SCENE STATE:',
            'Setting: ' + shared['setting'],
            'Visual invariants: ' + shared['visual_invariants'],
            'Source action: ' + state['source_action'],
            'Staging: ' + state['staging'],
            'Current prop state: ' + state['prop_state'],
            'Protect in composition: ' + state['protected_subjects'],
        ])
        editorial = state.get('editorial')
        if editorial is not None:
            if editorial.get('source_cut_id') != source['id']:
                raise ValueError('Editorial source differs: ' + source['id'])
            for field in ('intent', 'reader_information'):
                if not isinstance(editorial.get(field), str) or not editorial[field].strip():
                    raise ValueError('Missing editorial ' + field)
            for field in ('state_before', 'state_after'):
                value = editorial.get(field)
                if not isinstance(value, dict) or any(not isinstance(k, str) or not k.strip()
                        or not isinstance(v, str) or not v.strip() for k, v in value.items()):
                    raise ValueError('Invalid editorial ' + field)
            dependencies = editorial.get('depends_on')
            if not isinstance(dependencies, list) or len(set(dependencies)) != len(dependencies):
                raise ValueError('Invalid editorial dependencies')
            visible = editorial.get('visible_cast', [])
            if (not isinstance(visible, list) or any(not isinstance(v, str) or not v.strip() for v in visible)
                    or len(set(visible)) != len(visible)):
                raise ValueError('Invalid editorial visible cast')
            for dependency in dependencies:
                if dependency not in prior_states:
                    raise ValueError('Dependency must be an earlier annotated scene')
                for key, value in prior_states[dependency].items():
                    if key in editorial['state_before'] and editorial['state_before'][key] != value:
                        raise ValueError('Continuity state conflicts: ' + source['id'] + '/' + key)
            prior_states[source['id']] = editorial['state_after']
            result[source['id']] += '\n' + '\n'.join([
                'Source cut: ' + editorial['source_cut_id'],
                'Editorial intent (not a new story event): ' + editorial['intent'],
                'Reader information: ' + editorial['reader_information'],
                'State before: ' + json.dumps(editorial['state_before'], ensure_ascii=False, sort_keys=True),
                'State after: ' + json.dumps(editorial['state_after'], ensure_ascii=False, sort_keys=True),
                'Depends on: ' + ', '.join(dependencies),
            ])
    return result


def sequence_defects(root, job, cut_id=None):
    """Block an observed common defect across scenes; never infer visual approval."""
    path = root / 'sequence_defects.json'
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('episode_sha256') != hashlib.sha256((root / job['episode']).read_bytes()).hexdigest():
        raise ValueError('Sequence defect ledger is stale')
    ids = {c['id'] for c in job['cuts']}
    defects = data.get('defects')
    if not isinstance(defects, list):
        raise ValueError('Explicit sequence defect list required')
    blocked = []
    seen = set()
    for defect in defects:
        identifier = defect.get('id')
        affected = defect.get('affected_cuts')
        if (not isinstance(identifier, str) or not identifier.strip() or identifier in seen
                or not isinstance(affected, list) or not affected or any(c not in ids for c in affected)
                or len(set(affected)) != len(affected)):
            raise ValueError('Invalid sequence defect identity/scope')
        seen.add(identifier)
        for field in ('symptom', 'cause'):
            if not isinstance(defect.get(field), str) or not defect[field].strip():
                raise ValueError('Missing defect ' + field)
        status = defect.get('status')
        if status not in {'open', 'validation', 'resolved'}:
            raise ValueError('Invalid sequence defect status')
        if status == 'resolved':
            resolution = defect.get('resolution', {})
            observed = (root / resolution.get('image', '')).resolve()
            if (not observed.is_relative_to(root.resolve()) or not observed.is_file()
                    or observed.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}
                    or hashlib.sha256(observed.read_bytes()).hexdigest() != resolution.get('image_sha256')
                    or not isinstance(resolution.get('observation'), str) or not resolution['observation'].strip()):
                raise ValueError('Defect resolution needs bound observed image evidence')
            prompts = {c['id']: hashlib.sha256((root / c['prompt_file']).read_bytes()).hexdigest()
                       for c in job['cuts'] if c['id'] in affected}
            if resolution.get('prompt_sha256') != prompts:
                raise ValueError('Defect resolution prompts are stale')
            continue
        if cut_id is not None and cut_id not in affected:
            continue
        if status == 'validation' and cut_id == defect.get('validation_cut'):
            record = next(c for c in job['cuts'] if c['id'] == cut_id)
            current = hashlib.sha256((root / record['prompt_file']).read_bytes()).hexdigest()
            old = defect.get('failed_prompt_sha256')
            if (isinstance(old, str) and len(old) == 64 and old != current
                    and defect.get('validation_prompt_sha256') == current):
                continue
        blocked.append({'id': identifier, 'affected_cuts': affected,
                        'symptom': defect['symptom'], 'cause': defect['cause']})
    return blocked


def bound_context(root, job, cut_id):
    path = root / 'generation_context.json'
    if not path.exists():
        return None  # Historical jobs retain their exact request contract.
    data = path.read_bytes()
    binding = {'path': str(path.resolve()), 'sha256': hashlib.sha256(data).hexdigest()}
    # New production inputs must be in the reviewed workflow evidence.
    record = json.loads((root / job['workflow_review']).read_text(encoding='utf-8'))
    if not any(e.get('path') == binding['path'] and e.get('sha256') == binding['sha256']
               for e in record.get('evidence', [])):
        raise ValueError('Bind scene context to workflow evidence before generation')
    episode = (root / job['episode']).read_bytes()
    context = json.loads(data)
    brief = compile_context(episode, context)[cut_id]
    scene = next(s for s in context['scenes'] if s['id'] == cut_id)
    for identifier in scene.get('editorial', {}).get('visible_cast', []):
        character = job.get('characters', {}).get(identifier)
        if not isinstance(character, dict) or not isinstance(character.get('description'), str) or not character['description'].strip():
            raise ValueError('Visible cast needs an approved identity: ' + identifier)
        brief += '\nVisible character identity ' + identifier + ': ' + character['description']
    return brief


def repeated_failure(evidence, cut_id, failure_kind):
    if not failure_kind or not failure_kind.strip():
        raise ValueError('Explicit failure kind is required for a correction')
    recent = sorted(evidence.glob(cut_id + '_attempt*/REJECTION.json'))
    streak = 0
    for path in reversed(recent):
        record = json.loads(path.read_text(encoding='utf-8'))
        if record.get('failure_kind') != failure_kind:
            break
        streak += 1
    return streak >= 2


def pending_replan(root, cut_id, brief):
    path = root / 'generation_evidence' / (cut_id + '.replan.json')
    if not path.exists():
        return False
    pending = json.loads(path.read_text(encoding='utf-8'))
    resolution = root / 'generation_evidence' / (cut_id + '.replan_resolution.json')
    if not resolution.exists():
        return True
    result = json.loads(resolution.read_text(encoding='utf-8'))
    current = hashlib.sha256(brief.encode('utf-8')).hexdigest()
    return not (result.get('replan_sha256') == hashlib.sha256(path.read_bytes()).hexdigest()
                and result.get('revised_prompt_sha256') == current
                and current != pending['prompt_sha256']
                and isinstance(result.get('strategy'), str) and result['strategy'].strip())
