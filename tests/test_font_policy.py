"""Reject unlicensed overrides and preserve notices through actual delivery ZIPs."""
import hashlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile

from PIL import Image

from src import font_policy as fp
from src.ai_notice import package_review
from src.webtoon_stitcher import stitch_episode
from tools import setup_open_fonts


class OpenFontPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=fp.ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fixture(self, dialogue=None):
        Image.new('RGB', (800, 240), '#91ab9a').save(self.root / 'art.png')
        words = dialogue if dialogue is not None else [
            {'text': '오늘도 한 걸음.', 'position': 'top'},
            {'text': '좋아!', 'position': 'bottom', 'weight': 'bold'}]
        source = self.root / 'input.json'
        source.write_text(json.dumps({'title': 'Synthetic font check', 'cuts': [
            {'id': 'one', 'image': 'art.png', 'dialogue': words}]}), encoding='utf-8')
        return source

    def test_defaults_and_renamed_approved_bytes(self):
        self.assertEqual(fp.font_record(fp.entry_font({}))['weight'], 500)
        self.assertEqual(fp.font_record(fp.entry_font({'weight': 'bold'}))['weight'], 700)
        renamed = self.root / 'renamed.ttf'
        shutil.copyfile(fp.DEFAULT_FONT, renamed)
        self.assertEqual(fp.font_record(renamed), fp.font_record(fp.DEFAULT_FONT))

    def test_unapproved_overrides_and_changed_license_fail_before_output(self):
        unknown = self.root / 'Pretendard-Medium.otf'
        unknown.write_bytes(b'Unverified bytes despite approved-looking filename')
        for choose in [lambda: fp.resolve_font(unknown),
                       lambda: fp.entry_font({'font_path': str(unknown)}),
                       lambda: stitch_episode(self.fixture(), self.root / 'bad', font_path=unknown)]:
            with self.assertRaises(ValueError):
                choose()
        with patch.dict('os.environ', {'WEBTOON_FONT': str(unknown)}):
            with self.assertRaises(ValueError):
                fp.resolve_font()
        with patch.object(fp, 'LICENSE', unknown):
            with self.assertRaises(ValueError):
                fp.resolve_font(fp.DEFAULT_FONT)
        self.assertFalse((self.root / 'bad').exists())

    def test_notice_is_in_zip_and_original_body_and_source_files_are_preserved(self):
        source = self.fixture()
        assembly = stitch_episode(source, self.root / 'assembly')
        manifest = json.loads(assembly.read_text(encoding='utf-8'))
        self.assertEqual({f['weight'] for f in manifest['fonts_used']}, {500, 700})
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in assembly.parent.rglob('*') if p.is_file()}
        dest = self.root / 'delivery'
        package_review(assembly, dest)
        delivered = json.loads((dest / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(delivered['source_font_provenance'], 'verified')
        with zipfile.ZipFile(dest / 'review_images.zip') as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(hashlib.sha256(archive.read('licenses/Pretendard-OFL.txt')).hexdigest(),
                             fp.LICENSE_SHA256)
            metadata = json.loads(archive.read('font_licenses.json'))
            self.assertEqual(metadata['fonts'], delivered['fonts_used'])
            self.assertFalse(any(n.endswith(('.otf', '.ttf')) for n in archive.namelist()))
        with Image.open(assembly.parent / 'full_strip.png') as body, Image.open(dest / 'full_strip.png') as full:
            self.assertEqual(body.tobytes(), full.crop((0, delivered['body_offset_y'], 800, full.height)).tobytes())
        self.assertTrue(all(hashlib.sha256(p.read_bytes()).hexdigest() == digest for p, digest in before.items()))

    def test_lost_or_modified_source_notice_blocks_repackaging(self):
        assembly = stitch_episode(self.fixture(), self.root / 'assembly')
        license_file = assembly.parent / 'licenses/Pretendard-OFL.txt'
        license_file.write_text('Altered notice', encoding='utf-8')
        with self.assertRaises(ValueError):
            package_review(assembly, self.root / 'bad')
        license_file.unlink()
        with self.assertRaises((ValueError, OSError)):
            package_review(assembly, self.root / 'bad')
        self.assertFalse((self.root / 'bad').exists())

    def test_explicit_entry_override_cannot_bypass_the_policy(self):
        source = self.fixture([{'text': '대사', 'font_path': 'C:/Windows/Fonts/malgun.ttf'}])
        with self.assertRaises(ValueError):
            stitch_episode(source, self.root / 'bad')
        self.assertFalse((self.root / 'bad').exists())

    def test_partial_legacy_provenance_remains_legacy_after_packaging(self):
        assembly = stitch_episode(self.fixture(), self.root / 'assembly')
        manifest = json.loads(assembly.read_text(encoding='utf-8'))
        manifest['source_font_provenance'] = 'legacy_unverified'
        assembly.write_text(json.dumps(manifest), encoding='utf-8')
        dest = self.root / 'delivery'
        package_review(assembly, dest)
        self.assertEqual(json.loads((dest / 'manifest.json').read_text(encoding='utf-8'))[
            'source_font_provenance'], 'legacy_unverified')

    def test_setup_downloads_pinned_bytes_and_does_not_fetch_again(self):
        files = {setup_open_fonts.BASE + remote: (fp.FONT_DIR / name).read_bytes()
                 for name, (remote, _) in setup_open_fonts.FILES.items()}
        target = self.root / 'fonts'
        with patch.object(setup_open_fonts, 'FONT_DIR', target), patch.object(
                setup_open_fonts, 'urlopen', side_effect=lambda url, **kwargs: io.BytesIO(files[url])) as fetch:
            setup_open_fonts.setup()
            self.assertEqual(fetch.call_count, 3)
            setup_open_fonts.setup()
            self.assertEqual(fetch.call_count, 3)
        for name in setup_open_fonts.FILES:
            self.assertEqual((target / name).read_bytes(), (fp.FONT_DIR / name).read_bytes())

    def test_bad_download_never_publishes_font_assets(self):
        target = self.root / 'fonts'
        with patch.object(setup_open_fonts, 'FONT_DIR', target), patch.object(
                setup_open_fonts, 'urlopen', return_value=io.BytesIO(b'changed upstream file')):
            with self.assertRaises(ValueError):
                setup_open_fonts.setup()
        self.assertEqual(list(target.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
