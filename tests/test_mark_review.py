"""Synthetic pixel roundtrip, negative controls and immutable input files."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import random
import tempfile
import unittest

from PIL import Image
from tools.mark_review import init_key, main, mark_image, verify_image


class MarkReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.key = cls.root / 'private.key'
        cls.key.write_bytes(bytes(range(32)))
        cls.wrong_key = cls.root / 'wrong.key'
        cls.wrong_key.write_bytes(bytes(reversed(range(32))))
        rng = random.Random(217)
        source = Image.new('RGB', (512, 512))
        source.putdata([(v, v, v) for v in (rng.randrange(24, 232) for _ in range(512 * 512))])
        cls.source = cls.root / 'source.png'
        source.save(cls.source)
        cls.original_bytes = cls.source.read_bytes()
        cls.output = cls.root / 'marked.png'
        cls.owner = 'Private synthetic owner label'
        cls.work_id = 'Private synthetic work label'
        cls.report = mark_image(cls.source, cls.output, owner=cls.owner,
                                work_id=cls.work_id, key_file=cls.key, protected_top=64)

    def test_encoded_file_and_expected_report_roundtrip(self):
        report = verify_image(self.output, key_file=self.key,
                              expected_sha256=self.report['output_sha256'],
                              expected_asset_id=self.report['watermark']['asset_id'])
        self.assertEqual(report['status'], 'verified')
        self.assertTrue(report['expected_sha256_matches'])
        self.assertTrue(report['expected_asset_id_matches'])
        self.assertEqual(hashlib.sha256(self.output.read_bytes()).hexdigest(), self.report['output_sha256'])
        with Image.open(self.output) as marked, Image.open(self.source) as original:
            self.assertEqual(marked.crop((0, 0, 512, 64)).tobytes(), original.crop((0, 0, 512, 64)).tobytes())
            self.assertFalse(marked.info)

    def test_wrong_key_and_original_are_not_verified(self):
        self.assertEqual(verify_image(self.output, key_file=self.wrong_key)['status'], 'not_verified')
        self.assertEqual(verify_image(self.source, key_file=self.key)['status'], 'not_verified')
        self.assertEqual(verify_image(self.output, key_file=self.key, expected_sha256='0' * 64)['status'], 'not_verified')
        self.assertEqual(verify_image(self.output, key_file=self.key, expected_asset_id='0' * 16)['status'], 'not_verified')

    def test_original_key_and_existing_output_are_preserved(self):
        self.assertEqual(self.source.read_bytes(), self.original_bytes)
        self.assertEqual(self.key.read_bytes(), bytes(range(32)))
        original_output = self.output.read_bytes()
        for destination in (self.source, self.output):
            with self.assertRaises(FileExistsError):
                mark_image(self.source, destination, owner=self.owner, work_id=self.work_id, key_file=self.key)
        self.assertEqual(self.source.read_bytes(), self.original_bytes)
        self.assertEqual(self.output.read_bytes(), original_output)

    def test_missing_key_is_not_created_and_flat_image_is_not_issued(self):
        missing = self.root / 'missing.key'
        output = self.root / 'must_not_exist.png'
        with self.assertRaises(FileNotFoundError):
            mark_image(self.source, output, owner=self.owner, work_id=self.work_id, key_file=missing)
        self.assertFalse(missing.exists())
        flat = self.root / 'flat.png'
        Image.new('RGB', (512, 512), 'white').save(flat)
        with self.assertRaisesRegex(ValueError, 'Insufficient textured'):
            mark_image(flat, output, owner=self.owner, work_id=self.work_id, key_file=self.key)
        self.assertFalse(output.exists())

    def test_key_initialization_is_explicit_exclusive_and_status_only(self):
        path = self.root / 'new-private-area' / 'generated.key'
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(['init-key', str(path)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stream.getvalue()), {'status': 'key_created'})
        key = path.read_bytes()
        self.assertEqual(len(key), 32)
        self.assertNotEqual(key, bytes(32))
        with self.assertRaises(FileExistsError):
            init_key(path)
        self.assertEqual(path.read_bytes(), key)
        with self.assertRaises(FileExistsError):
            init_key(self.key)
        self.assertEqual(self.key.read_bytes(), bytes(range(32)))

    def test_cli_does_not_report_private_labels_or_paths(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(['embed', str(self.source), str(self.root / 'cli.png'), '--owner', self.owner,
                         '--work-id', self.work_id, '--key-file', str(self.key)])
        report_text = stream.getvalue()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(report_text)['status'], 'marked_and_verified')
        for secret in (self.owner, self.work_id, str(self.key), self.key.read_bytes().hex()):
            self.assertNotIn(secret, report_text)
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(['verify', str(self.output), '--key-file', str(self.root / 'missing.key')])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stream.getvalue()), {'status': 'error', 'error': 'required_file_missing'})


if __name__ == '__main__':
    unittest.main()
