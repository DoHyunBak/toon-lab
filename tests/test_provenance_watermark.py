"""Pixel-only detection, negative controls and bounded RGB changes."""
import io
import random
import unittest
from PIL import Image, ImageChops
from src.provenance_watermark import embed, detect


class ProvenanceWatermarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = random.Random(217)
        cls.source = Image.new('RGB',(512,512))
        cls.source.putdata([(v,v,v) for v in (rng.randrange(24,232) for _ in range(512*512))])
        cls.key = bytes(range(32))
        cls.asset = b'asset001'
        cls.marked,cls.record = embed(cls.source,cls.key,cls.asset)

    def test_roundtrip_without_any_metadata(self):
        stream = io.BytesIO()
        self.marked.save(stream,format='PNG')
        stream.seek(0)
        reopened = Image.open(stream)
        self.assertFalse(reopened.info)
        self.assertEqual(detect(reopened,self.key)['asset_id'],self.asset.hex())

    def test_negative_controls_do_not_claim_provenance(self):
        self.assertFalse(detect(self.source,self.key)['detected'])
        self.assertFalse(detect(self.marked,bytes(reversed(self.key)))['detected'])
        self.assertFalse(detect(Image.new('RGB',(512,512),'white'),self.key)['detected'])
        with self.assertRaisesRegex(ValueError,'Insufficient textured'):
            embed(Image.new('RGB',(512,512),'white'),self.key,self.asset)

    def test_delivery_copy_only_and_bounded_changes(self):
        before = self.source.tobytes()
        embed(self.source,self.key,self.asset)
        self.assertEqual(before,self.source.tobytes())
        self.assertLessEqual(max(high for low,high in ImageChops.difference(self.source,self.marked).getextrema()),4)

    def test_rgb_contract_and_protected_notice(self):
        with self.assertRaisesRegex(ValueError,'explicit RGB'):
            embed(self.source.convert('RGBA'),self.key,self.asset)
        marked,_ = embed(self.source,self.key,self.asset,protected_top=64)
        self.assertEqual(marked.crop((0,0,512,64)).tobytes(),self.source.crop((0,0,512,64)).tobytes())


if __name__=='__main__':
    unittest.main()
