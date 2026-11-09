"""Reviewed workflow adoption preserves real screening history and all pixel QA gates."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image

from src.factory import prepare_job,import_cut,build_job
from src.operations import next_action,submit_review
from src.workflow_policy import adopt_workflow,VERSION


def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False),encoding='utf-8')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


class WorkflowPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='workflow-policy-',dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.job=self.root/'job'
        self.source=self.root/'source.json';save(self.source,dict(title='Synthetic policy fixture',cuts=[dict(id='fixture',description='Synthetic rectangle',dialogue=[],characters=[])]))
        prepare_job(self.source,self.job)
        self.evidence=self.root/'evidence.md';self.evidence.write_text('Synthetic authorization fixture, not real art approval',encoding='utf-8')
        self.record=self.root/'record.json';self.data=dict(version=VERSION,legal_review_trigger='workflow_changes_or_rights_reports',
            reviewer='Synthetic test observer',rights_basis='Synthetic owned fixture',license_conditions='No external art',
            permitted_external_processing='None in tests',review_scope='Control-flow test only',holds=[],
            evidence=[dict(path=str(self.evidence),sha256=digest(self.evidence))]);save(self.record,self.data)

    def test_adoption_changes_routing_without_faking_jev_pass(self):
        self.assertEqual(next_action(self.job)['action'],'legal_check')
        self.assertEqual(adopt_workflow(self.job,self.record)['status'],'reviewed')
        action=next_action(self.job);self.assertEqual(action['action'],'generate')
        self.assertNotIn('referenced_image_paths',action['imagegen'])
        self.assertFalse((self.job/'legal_preflight.check.json').exists())

    def test_stale_evidence_and_explicit_rights_holds_block(self):
        adopt_workflow(self.job,self.record);self.evidence.write_text('Changed',encoding='utf-8')
        self.assertEqual(next_action(self.job)['action'],'resolve_workflow_review')
        self.data['evidence'][0]['sha256']=digest(self.evidence);self.data['holds']=['Unresolved fixture rights issue'];save(self.record,self.data)
        self.assertEqual(adopt_workflow(self.job,self.record)['status'],'held')
        self.assertEqual(next_action(self.job)['action'],'resolve_workflow_review')

    def test_input_or_mode_tampering_cannot_use_adoption(self):
        adopt_workflow(self.job,self.record)
        p=self.job/'prompts/fixture.txt';p.write_text(p.read_text(encoding='utf-8')+'changed',encoding='utf-8')
        self.assertEqual(next_action(self.job)['action'],'resolve_workflow_review')
        j=json.loads((self.job/'job.json').read_text(encoding='utf-8'));j['generation_input_mode']='legacy_unverified';save(self.job/'job.json',j)
        with self.assertRaises(ValueError):next_action(self.job)

    def test_extensionless_license_is_valid_but_secret_inputs_are_rejected(self):
        license_path=self.root/'LICENSE';license_path.write_text('Synthetic license fixture',encoding='utf-8')
        self.data['evidence']=[dict(path=str(license_path),sha256=digest(license_path))];save(self.record,self.data)
        self.assertEqual(adopt_workflow(self.job,self.record)['status'],'reviewed')
        secret_path=self.root/'.env.txt';secret_path.write_text('Synthetic placeholder only',encoding='utf-8')
        self.data['evidence']=[dict(path=str(secret_path),sha256=digest(secret_path))];save(self.record,self.data)
        with self.assertRaisesRegex(ValueError,'disallowed'):adopt_workflow(self.job,self.record)

    def test_build_and_observed_review_remain_required_before_ready(self):
        adopt_workflow(self.job,self.record);action=next_action(self.job)
        art=self.root/'art.png';Image.new('RGB',(64,96),'#597a83').save(art)
        prompt=self.root/'actual.txt';prompt.write_text(action['imagegen']['prompt'],encoding='utf-8')
        import_cut(self.job,'fixture',art,prompt,used_reference_ids=[])
        self.assertEqual(next_action(self.job)['action'],'build')
        build_job(self.job,self.root/'output');self.assertEqual(next_action(self.job)['action'],'review')
        report=json.loads((self.job/'review.json').read_text(encoding='utf-8'))
        for c in report['cuts'].values():
            for check in c['checks'].values():check.update(result='pass',note='Synthetic fixture observation only')
        observed=self.root/'observed.json';save(observed,report);submit_review(self.job,observed)
        ready=next_action(self.job);self.assertEqual(ready['action'],'ready');self.assertFalse(ready['routine_jev_required'])
        self.assertEqual(ready['actual_legal_screenings']['preflight']['status'],'not_checked')
        self.assertEqual(ready['legal_clearance'],'not_issued')


if __name__=='__main__':unittest.main()
