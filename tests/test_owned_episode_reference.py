"""Synthetic control fixtures only: no image generation or real-art approval in these tests."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from PIL import Image
from src.factory import prepare_job, import_cut, build_job
from src.operations import next_action, submit_review
from src.owned_episode_reference import MODE
from src.workflow_policy import adopt_workflow, VERSION


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class OwnedEpisodeReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='owned-reference-test-',dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.job=self.root/'job'
        own=self.root/'own_episode1';own.mkdir();self.origin=own/'source.png'
        Image.new('RGB',(64,64),'#836f54').save(self.origin)
        self.catalog_root=self.root/'catalog';folder=self.catalog_root/'ref_1001';folder.mkdir(parents=True)
        original=folder/'original.png';shutil.copyfile(self.origin,original)
        self.benchmark=self.root/'benchmark.json';save(self.benchmark,{'approval':'approved','scope':'synthetic fixture, not user/art approval'})
        self.auth=self.catalog_root/'authorization.json'
        save(self.auth,{'scope':'own_episode1_outputs_only','user_authorized':True,'source_episode_id':'ep001',
                        'source_root':str(own),'permitted_actions':['imagegen_reference'],'holds':[],
                        'style_benchmark':{'path':str(self.benchmark),'sha256':sha(self.benchmark)}})
        self.metadata=folder/'metadata.json'
        self.meta={'id':'ref_1001','title':'Synthetic permission fixture','original':{'path':'original.png','sha256':sha(original),
                   'format':'PNG','width':64,'height':64,'bytes':original.stat().st_size},
                   'observations':[{'topic':'synthetic','note':'Control fixture only'}],'production_application':{},
                   'owned_source':{'episode_id':'ep001','path':str(self.origin),'sha256':sha(self.origin),'holds':[],
                                   'review_status':'reviewed_for_internal_reference_use','permitted_actions':['imagegen_reference']}}
        self.catalog=self.catalog_root/'catalog.json'
        self.cat={'schema_version':1,'usage_mode':MODE,'authorization':{'path':'authorization.json','sha256':sha(self.auth)},
                  'references':[{'id':'ref_1001','title':self.meta['title'],'original':'ref_1001/original.png',
                                 'metadata':'ref_1001/metadata.json','sha256':sha(original),'tags':['synthetic']}]}
        self.sync_metadata()
        self.source=self.root/'source.json'
        self.episode={'title':'Synthetic control fixture','generation_input_mode':MODE,'reference_ids':['ref_1001'],
                      'cuts':[{'id':'fixture','description':'Synthetic rectangle, not production artwork','dialogue':[],'characters':[]}]}
        save(self.source,self.episode)
        evidence=self.root/'evidence.md';evidence.write_text('Synthetic test policy evidence only',encoding='utf-8')
        self.record=self.root/'record.json'
        save(self.record,{'version':VERSION,'legal_review_trigger':'workflow_changes_or_rights_reports','reviewer':'test fixture',
                         'rights_basis':'synthetic fixture','license_conditions':'synthetic fixture','permitted_external_processing':'none in tests',
                         'review_scope':'control behavior, not real legal/art clearance','holds':[],
                         'evidence':[{'path':str(evidence),'sha256':sha(evidence)}]})

    def sync_metadata(self):
        save(self.metadata,self.meta)
        self.cat['references'][0]['metadata_sha256']=sha(self.metadata)
        save(self.catalog,self.cat)

    def prepare(self):
        prepare_job(self.source,self.job,reference_catalog=self.catalog)
        adopt_workflow(self.job,self.record)

    def import_fixture(self):
        action=next_action(self.job)
        art=self.root/'output_fixture.png';Image.new('RGB',(64,96),'#467b80').save(art)
        prompt=self.root/'actual.txt';prompt.write_text(action['imagegen']['prompt'],encoding='utf-8')
        return art,prompt

    def test_explicit_owned_request_contains_only_the_pinned_reference(self):
        self.prepare();action=next_action(self.job)
        self.assertEqual(action['generation_input_mode'],MODE)
        self.assertEqual(action['used_reference_ids'],['ref_1001'])
        self.assertEqual(len(action['imagegen']['referenced_image_paths']),1)
        self.assertEqual(sha(action['imagegen']['referenced_image_paths'][0]),sha(self.origin))
        self.assertNotIn('num_last_images_to_include',action['imagegen'])
        self.assertNotIn('Use text prompts only',action['imagegen']['prompt'])

    def test_owned_generation_requires_explicit_workflow_adoption(self):
        prepare_job(self.source,self.job,reference_catalog=self.catalog)
        self.assertEqual(next_action(self.job)['action'],'adopt_workflow')

    def test_import_cannot_claim_no_images_or_omit_actual_prompt(self):
        self.prepare();art,prompt=self.import_fixture()
        with self.assertRaises(ValueError):import_cut(self.job,'fixture',art,prompt,used_reference_ids=[])
        with self.assertRaises(ValueError):import_cut(self.job,'fixture',art,used_reference_ids=['ref_1001'])
        imported=import_cut(self.job,'fixture',art,prompt,used_reference_ids=['ref_1001'])
        self.assertEqual(imported['generation_input_mode'],MODE)
        self.assertEqual(next_action(self.job)['action'],'build')

    def test_origin_changes_block_even_if_catalog_copy_did_not_change(self):
        self.prepare();Image.new('RGB',(64,64),'#234567').save(self.origin)
        with self.assertRaisesRegex(ValueError,'origin/permission'):next_action(self.job)

    def test_same_image_hash_does_not_authorize_outside_source_scope(self):
        outside=self.root/'outside.png';shutil.copyfile(self.origin,outside)
        self.meta['owned_source']['path']=str(outside);self.sync_metadata()
        with self.assertRaisesRegex(ValueError,'outside own episode1'):self.prepare()

    def test_source_mode_alone_cannot_authorize_a_catalog_or_unapproved_benchmark(self):
        self.cat['usage_mode']='legacy_visual_examples';save(self.catalog,self.cat)
        with self.assertRaisesRegex(ValueError,'not an authorized'):self.prepare()
        self.cat['usage_mode']=MODE
        save(self.benchmark,{'approval':'pending'})
        auth=json.loads(self.auth.read_text(encoding='utf-8'));auth['style_benchmark']['sha256']=sha(self.benchmark)
        save(self.auth,auth);self.cat['authorization']['sha256']=sha(self.auth);save(self.catalog,self.cat)
        with self.assertRaisesRegex(ValueError,'Style benchmark'):self.prepare()

    def test_rights_holds_and_unlisted_input_mechanisms_are_rejected(self):
        self.meta['owned_source']['holds']=['Synthetic unresolved component'];self.sync_metadata()
        with self.assertRaises(ValueError):self.prepare()
        self.meta['owned_source']['holds']=[];self.sync_metadata()
        self.episode['cuts'][0]['atari']='unlisted-input.png';save(self.source,self.episode)
        with self.assertRaises(ValueError):self.prepare()

    def test_actual_reference_declaration_tampering_blocks_handoff(self):
        self.prepare();art,prompt=self.import_fixture();import_cut(self.job,'fixture',art,prompt,used_reference_ids=['ref_1001'])
        p=self.job/'job.json';job=json.loads(p.read_text(encoding='utf-8'))
        job['cuts'][0]['imported']['visual_reference_usage']['ids']=[];save(p,job)
        with self.assertRaisesRegex(ValueError,'Actual reference use'):next_action(self.job)

    def test_owned_mode_still_needs_current_build_and_seven_criterion_review(self):
        self.prepare();art,prompt=self.import_fixture();import_cut(self.job,'fixture',art,prompt,used_reference_ids=['ref_1001'])
        build_job(self.job,self.root/'output');self.assertEqual(next_action(self.job)['action'],'review')
        review=json.loads((self.job/'review.json').read_text(encoding='utf-8'))
        for c in review['cuts'].values():
            for item in c['checks'].values():item.update(result='pass',note='Synthetic fixture control observation only')
        report=self.root/'observed.json';save(report,review);submit_review(self.job,report)
        ready=next_action(self.job)
        self.assertEqual(ready['action'],'ready');self.assertEqual(ready['generation_input_mode'],MODE)
        self.assertEqual(ready['legal_clearance'],'not_issued');self.assertFalse(ready['routine_jev_required'])


if __name__=='__main__':unittest.main()
