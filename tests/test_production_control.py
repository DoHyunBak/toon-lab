import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from src.production_control import compile_context, replace_correction, repeated_failure, pending_replan, sequence_defects, bound_context, CORRECTION


class ProductionControlTests(unittest.TestCase):
    def fixture(self):
        episode = json.dumps({'cuts':[{'id':'a','description':'The first light goes dark'},
                                      {'id':'b','description':'Look at the door'}]}).encode()
        context = dict(episode_sha256=hashlib.sha256(episode).hexdigest(),
            shared=dict(setting='Dark cavern',visual_invariants='Same stone door'),
            scenes=[dict(id=c['id'],source_action=c['description'],staging='Source camera',
                         prop_state='As specified',protected_subjects='Faces and clue')
                    for c in json.loads(episode)['cuts']])
        return episode, context

    def test_shared_setting_reaches_every_scene(self):
        episode, context = self.fixture()
        self.assertTrue(all('Setting: Dark cavern' in t for t in compile_context(episode,context).values()))

    def test_stale_source_and_missing_scene_rejected(self):
        episode, context = self.fixture()
        with self.assertRaises(ValueError): compile_context(episode+b' ',context)
        context['scenes'].pop()
        with self.assertRaises(ValueError): compile_context(episode,context)

    def test_source_event_cannot_be_rewritten(self):
        episode, context = self.fixture()
        context['scenes'][0]['source_action']='Change the story'
        with self.assertRaises(ValueError): compile_context(episode,context)

    def test_editorial_reason_reaches_prompt_and_conflicting_dependency_is_rejected(self):
        episode, context = self.fixture()
        for index, scene in enumerate(context['scenes']):
            scene['editorial'] = dict(source_cut_id=scene['id'], intent='Make the door clue readable',
                reader_information='The first light has gone dark',
                state_before={'light': 'dark'}, state_after={'light': 'dark'},
                depends_on=['a'] if index else [])
        compiled = compile_context(episode, context)
        self.assertIn('Make the door clue readable', compiled['b'])
        context['scenes'][1]['editorial']['state_before']['light'] = 'bright'
        with self.assertRaisesRegex(ValueError, 'Continuity state conflicts'):
            compile_context(episode, context)
        context['scenes'][1]['editorial']['state_before']['light'] = 'dark'
        context['scenes'][0]['editorial']['depends_on'] = ['b']
        with self.assertRaisesRegex(ValueError, 'earlier annotated scene'):
            compile_context(episode, context)

    def test_common_defect_blocks_next_scene_until_changed_trial_and_bound_resolution(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            episode, _ = self.fixture()
            (root/'episode.json').write_bytes(episode)
            for name in ('a', 'b'):
                (root/(name+'.txt')).write_text('old', encoding='utf-8')
            job = {'episode':'episode.json', 'cuts':[{'id':n,'prompt_file':n+'.txt'} for n in ('a','b')]}
            defect = dict(id='shared-light', affected_cuts=['a','b'], symptom='Wrong light',
                cause='Stale shared state', status='open')
            ledger = dict(episode_sha256=hashlib.sha256(episode).hexdigest(), defects=[defect])
            def save(): (root/'sequence_defects.json').write_text(json.dumps(ledger), encoding='utf-8')
            save()
            self.assertEqual(sequence_defects(root,job,'b')[0]['id'], 'shared-light')
            defect.update(status='validation',validation_cut='a',failed_prompt_sha256=hashlib.sha256(b'old').hexdigest())
            (root/'a.txt').write_text('corrected', encoding='utf-8')
            defect['validation_prompt_sha256']=hashlib.sha256(b'corrected').hexdigest()
            save()
            self.assertEqual(sequence_defects(root,job,'a'), [])
            self.assertTrue(sequence_defects(root,job,'b'))
            self.assertTrue(sequence_defects(root,job))
            Image.new('RGB',(8,8)).save(root/'observed.png')
            defect.update(status='resolved',resolution=dict(image='observed.png',
                image_sha256=hashlib.sha256((root/'observed.png').read_bytes()).hexdigest(),
                observation='Synthetic control fixture, not real art QA',
                prompt_sha256={n:hashlib.sha256((root/(n+'.txt')).read_bytes()).hexdigest() for n in ('a','b')}))
            save()
            self.assertEqual(sequence_defects(root,job), [])
            (root/'b.txt').write_text('changed', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'prompts are stale'):
                sequence_defects(root,job)

    def test_explicit_visible_cast_supplies_approved_identity_and_rejects_unknown_actor(self):
        episode, context = self.fixture()
        context['scenes'][0]['editorial'] = dict(source_cut_id='a',intent='Read the group action',
            reader_information='Current source group only',state_before={},state_after={},depends_on=[],visible_cast=['otter'])
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'episode.json').write_bytes(episode)
            job=dict(episode='episode.json',workflow_review='workflow.json',
                     characters={'otter':{'description':'Warm-brown river otter with cream muzzle'}})
            def save():
                path=root/'generation_context.json';path.write_text(json.dumps(context),encoding='utf-8')
                (root/'workflow.json').write_text(json.dumps({'evidence':[dict(path=str(path.resolve()),
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest())]}),encoding='utf-8')
            save()
            self.assertIn('Warm-brown river otter with cream muzzle',bound_context(root,job,'a'))
            context['scenes'][0]['editorial']['visible_cast']=['invented'];save()
            with self.assertRaisesRegex(ValueError,'approved identity'):
                bound_context(root,job,'a')

    def test_required_prop_and_staging_cannot_be_empty(self):
        episode, context = self.fixture()
        context['scenes'][0]['prop_state']=''
        with self.assertRaises(ValueError): compile_context(episode,context)

    def test_correction_replaces_conflicting_older_instructions(self):
        text='Original brief'+CORRECTION+'Full ring'+CORRECTION+'Crop the ring'
        result=replace_correction(text,'Show only first dark light')
        self.assertEqual(result.count(CORRECTION),1)
        self.assertNotIn('Full ring',result)
        self.assertNotIn('Crop the ring',result)

    def test_two_same_failures_require_replan(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for i,kind in enumerate(['prop','setting','setting']):
                p=root/f'a_attempt{i:03d}';p.mkdir()
                (p/'REJECTION.json').write_text(json.dumps({'failure_kind':kind}))
            self.assertTrue(repeated_failure(root,'a','setting'))
            self.assertFalse(repeated_failure(root,'a','prop'))

    def test_replan_requires_changed_prompt_and_bound_strategy(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);e=root/'generation_evidence';e.mkdir()
            p=e/'a.replan.json';p.write_text(json.dumps({'prompt_sha256':hashlib.sha256(b'old').hexdigest()}))
            self.assertTrue(pending_replan(root,'a','old'))
            r={'replan_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
               'revised_prompt_sha256':hashlib.sha256(b'new').hexdigest(),'strategy':'Change the camera'}
            (e/'a.replan_resolution.json').write_text(json.dumps(r))
            self.assertFalse(pending_replan(root,'a','new'))
            self.assertTrue(pending_replan(root,'a','old'))


if __name__ == '__main__': unittest.main()
