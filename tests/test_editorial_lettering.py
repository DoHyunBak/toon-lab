"""Renderer contracts, not visual-quality scores."""
import unittest
from PIL import Image, ImageChops
from src.bubble_renderer import render_bubbles, BubbleLayoutError

class EditorialLetteringTests(unittest.TestCase):
    def test_tail_attachment_is_slender_and_reaches_speaker(self):
        from src.editorial_lettering import _outline
        import math
        tip=(250,350);points=_outline((100,100,400,280),'normal',tip)
        self.assertLess(math.dist(points[0],points[160]),24)
        self.assertIn(tip,points)

    def test_curve_overlay_preserves_source_and_distant_art(self):
        source=Image.new('RGB',(800,600),'#597a83');before=source.tobytes()
        result=render_bubbles(source,[{'style':'editorial','type':'normal','text':'너부터.',
            'box':[.10,.10,.30,.20],'tail':[.48,.34],'font_size':30}],min_font_size=24)
        self.assertEqual(source.tobytes(),before)
        self.assertEqual(result.size,source.size)
        self.assertIsNotNone(ImageChops.difference(result,source).getbbox())
        self.assertEqual(result.crop((600,450,800,600)).tobytes(),source.crop((600,450,800,600)).tobytes())

    def test_text_overflow_and_mixed_modes_fail_instead_of_publishing_bad_art(self):
        source=Image.new('RGB',(800,600),'white')
        e={'style':'editorial','type':'normal','text':'너부터.','box':[.1,.1,.3,.2],'font_size':30}
        with self.assertRaises(BubbleLayoutError):
            render_bubbles(source,[{**e,'text':'긴 대사'*100}],min_font_size=24)
        with self.assertRaises(BubbleLayoutError):
            render_bubbles(source,[e,{'text':'다른 형식'}],min_font_size=24)

    def test_tail_and_sfx_validate_before_returning_output(self):
        source=Image.new('RGB',(800,600),'white')
        with self.assertRaises(BubbleLayoutError):
            render_bubbles(source,[{'style':'editorial','text':'응','box':[.1,.1,.3,.2],
                'tail':[.2,.2],'font_size':30}],min_font_size=24)
        with self.assertRaises(BubbleLayoutError):
            render_bubbles(source,[{'style':'editorial','type':'sfx','text':'톡','box':[.1,.1,.3,.2],
                'angle':float('nan'),'font_size':30}],min_font_size=24)

    def test_transparency_and_angled_sfx(self):
        source=Image.new('RGBA',(800,600),(0,0,0,0))
        result=render_bubbles(source,[{'style':'editorial','type':'sfx','text':'톡','box':[.1,.1,.4,.3],
            'angle':12,'font_size':42}],min_font_size=24)
        self.assertEqual(result.mode,'RGBA')
        self.assertEqual(result.getpixel((799,599))[3],0)
        self.assertIsNotNone(result.getbbox())
