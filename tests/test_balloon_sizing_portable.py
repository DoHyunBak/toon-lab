"""Portable typography safety tests with synthetic text and an installed font."""
import unittest

from src.balloon_sizing import measure_balloon

SAMPLES = ['한 줄 시험', '첫 번째 측정 문장\n두 번째 줄',
           '여러 줄 식자 검증\n곡면 안쪽 여백 확인\n마지막 줄 시험']


class BalloonSizingPortableTests(unittest.TestCase):
    def test_explicit_variants_preserve_type_and_differ_in_spacing(self):
        for text in SAMPLES:
            b = measure_balloon(text, font_path=None, variant='B')
            c = measure_balloon(text, font_path=None, variant='C')
            self.assertEqual(b.font_size, c.font_size)
            self.assertEqual(b.font_size, 32)
            self.assertGreater(c.width, b.width)
            self.assertGreaterEqual(c.height, b.height)

    def test_equal_character_counts_do_not_force_equal_widths(self):
        self.assertLess(measure_balloon('iiiiiiii', font_path=None).width,
                        measure_balloon('WWWWWWWW', font_path=None).width)

    def test_corner_safety_for_varied_line_shapes_and_sizes(self):
        for text in SAMPLES + ['긴 첫 줄의 문장을 확인합니다.\n짧게', '짧게\n마지막 줄의 곡면을 확인합니다.', '앗!', '…?!']:
            for size in (24, 32, 40):
                for variant in ('B', 'C'):
                    result = measure_balloon(text, font_path=None, font_size=size, variant=variant)
                    for left, top, right, bottom in result.text_boxes:
                        for x in (left, right):
                            for y in (top, bottom):
                                ellipse = ((x-result.width/2)/(result.width/2))**2 + ((y-result.height/2)/(result.height/2))**2
                                self.assertLess(ellipse, 1)

    def test_width_limit_requires_edit_instead_of_font_shrink(self):
        result = measure_balloon(SAMPLES[2], font_path=None)
        with self.assertRaisesRegex(ValueError, 'without shrinking'):
            measure_balloon(SAMPLES[2], font_path=None, max_width=result.width-1)
        exact = measure_balloon(SAMPLES[2], font_path=None, max_width=result.width)
        self.assertEqual(exact, result)

    def test_invalid_input_does_not_silently_substitute_defaults(self):
        for kwargs in ({'variant': 'A'}, {'font_size': 0}, {'font_size': 2.5}):
            with self.assertRaises(ValueError):
                measure_balloon('시험', font_path=None, **kwargs)
        for text in ('', '  ', '시험\n\n다음'):
            with self.assertRaises(ValueError):
                measure_balloon(text, font_path=None)

    def test_editorial_body_follows_measurements_and_preserves_source_art(self):
        from PIL import Image, ImageChops
        from src.bubble_renderer import render_bubbles, BubbleLayoutError
        source = Image.new('RGB', (800, 600), '#789abc')
        before = source.tobytes()
        for variant in ('B', 'C'):
            measured = measure_balloon(SAMPLES[1], font_path=None, variant=variant)
            entry = dict(style='editorial', type='normal', text=SAMPLES[1], font_size=32,
                         balloon_variant=variant,
                         box=[100/800, 40/600, measured.width/800, measured.height/600], tail=[.45, .55])
            result = render_bubbles(source, [entry], font_path=None)
            self.assertEqual(source.tobytes(), before)
            self.assertIsNotNone(ImageChops.difference(source, result).getbbox())
            self.assertEqual(source.crop((650, 450, 800, 600)).tobytes(),
                             result.crop((650, 450, 800, 600)).tobytes())
            with self.assertRaisesRegex(BubbleLayoutError, 'measured dimensions'):
                render_bubbles(source, [{**entry, 'box': [.1, .1, .2, .2]}], font_path=None)


if __name__ == '__main__':
    unittest.main()
