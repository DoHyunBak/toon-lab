"""ComfyUI output must keep its real provider and exact generation evidence."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from src.factory import import_cut, prepare_job
from src.operations import _provenance


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ComfyFactoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        episode = self.root / 'episode.json'
        episode.write_text(json.dumps({'title': 'Protocol fixture', 'cuts': [
            {'id': 'cut_a', 'page': 1, 'description': 'A blank studio door', 'characters': [], 'dialogue': []}
        ]}), encoding='utf-8')
        self.job = self.root / 'job'
        prepare_job(episode, self.job)
        self.run = self.root / 'run'
        self.run.mkdir()
        self.image = self.run / 'image.png'
        Image.new('RGB', (256, 256), '#acc9db').save(self.image)
        self.workflow = self.run / 'workflow_api.json'
        self.workflow.write_text(json.dumps({
            '1': {'class_type': 'VAEDecode', 'inputs': {}},
            '2': {'class_type': 'SaveImage', 'inputs': {'images': ['1', 0], 'filename_prefix': 'fixture'}}
        }), encoding='utf-8')
        self.receipt = self.run / 'receipt.json'
        self.record = {'schema_version': 1, 'provider': 'comfyui', 'status': 'completed',
                       'server': 'http://127.0.0.1:8188', 'prompt_id': 'fixture-prompt',
                       'workflow': {'path': 'workflow_api.json', 'sha256': digest(self.workflow)},
                       'output_node_id': '2',
                       'output': {'path': 'image.png', 'sha256': digest(self.image), 'width': 256, 'height': 256}}
        self.save_receipt()
        self.prompt = self.root / 'actual.txt'
        self.prompt.write_text('Actual graph prompt fixture; no image inputs.', encoding='utf-8')

    def save_receipt(self):
        self.receipt.write_text(json.dumps(self.record), encoding='utf-8')

    def import_image(self, **kwargs):
        return import_cut(self.job, 'cut_a', self.image, self.prompt, provider='comfyui',
                          used_reference_ids=[], generation_record=self.receipt, **kwargs)

    def test_real_provider_and_frozen_evidence_survive_run_directory_changes(self):
        imported = self.import_image()
        self.assertEqual(imported['provider'], 'comfyui')
        evidence = imported['generation_record']
        self.assertEqual((self.job / evidence['workflow']['path']).read_bytes(), self.workflow.read_bytes())
        self.assertEqual((self.job / evidence['receipt']['path']).read_bytes(), self.receipt.read_bytes())
        self.workflow.write_text('changed outside job', encoding='utf-8')
        job = json.loads((self.job / 'job.json').read_text(encoding='utf-8'))
        self.assertEqual(_provenance(job, self.job), [])
        (self.job / evidence['workflow']['path']).write_text('tampered', encoding='utf-8')
        self.assertTrue(any('ComfyUI' in s for s in _provenance(job, self.job)))

    def test_incomplete_receipt_and_changed_output_do_not_register_art(self):
        before = (self.job / 'job.json').read_bytes()
        self.record['status'] = 'submitted'
        self.save_receipt()
        with self.assertRaises(ValueError):
            self.import_image()
        self.record['status'] = 'completed'
        self.save_receipt()
        Image.new('RGB', (256, 256), 'red').save(self.image)
        with self.assertRaises(ValueError):
            self.import_image()
        self.assertEqual((self.job / 'job.json').read_bytes(), before)

    def test_explicit_receipt_and_nonuse_declaration_are_required(self):
        with self.assertRaises(ValueError):
            import_cut(self.job, 'cut_a', self.image, self.prompt, provider='comfyui')
        with self.assertRaises(ValueError):
            import_cut(self.job, 'cut_a', self.image, self.prompt, provider='comfyui', generation_record=self.receipt)

    def test_image_input_and_unknown_nodes_cannot_be_declared_text_only(self):
        for class_type in ('LoadImage', 'ControlNetApply', 'UnknownCustomNode'):
            graph = json.loads(self.workflow.read_text(encoding='utf-8'))
            graph['1']['class_type'] = class_type
            self.workflow.write_text(json.dumps(graph), encoding='utf-8')
            self.record['workflow']['sha256'] = digest(self.workflow)
            self.save_receipt()
            with self.assertRaisesRegex(ValueError, 'audited core'):
                self.import_image()


if __name__ == '__main__':
    unittest.main()
