"""Standalone B/C text-measured oval sizing; does not change production rendering."""
from dataclasses import dataclass
import math

from .bubble_renderer import _load_font


@dataclass(frozen=True)
class BalloonSize:
    variant: str
    width: int
    height: int
    font_size: int
    line_gap: float
    text_boxes: tuple[tuple[float, float, float, float], ...]


def measure_balloon(text, *, font_path, font_size=32, variant="B", max_width=None):
    """Preserve authored lines/font size; raise when wrapping or splitting is needed.

    text_boxes are relative to the body, excluding stroke and tail. Variant is
    an explicit editorial choice, never inferred from dialogue meaning/length.
    """
    if variant not in ("B", "C"):
        raise ValueError("variant must be B or C")
    if not isinstance(font_size, int) or font_size <= 0:
        raise ValueError("font_size must be a positive integer")
    lines = text.split("\n")
    if any(not line.strip() for line in lines):
        raise ValueError("Supply nonempty authored lines; split blank paragraphs separately")
    scale = 4
    font = _load_font(font_path, font_size * scale, text)
    bounds = [font.getbbox(line) for line in lines]
    widths = [(b[2] - b[0]) / scale for b in bounds]
    heights = [(b[3] - b[1]) / scale for b in bounds]
    gap = font_size * .28
    block = sum(heights) + gap * (len(lines) - 1)
    extra, padding = (4 * font_size, .625 * font_size) if variant == "B" else (5 * font_size, .875 * font_size)
    width = math.ceil((max(widths) + extra) / 4) * 4
    if max_width is not None and width > max_width:
        raise ValueError("Balloon exceeds max_width; review line breaks or split dialogue without shrinking text")
    required = block + 2 * padding
    top = -block / 2
    for tw, th in zip(widths, heights):
        half_x = tw / 2 + padding
        half_y = max(abs(top), abs(top + th)) + padding
        required = max(required, 2 * half_y / math.sqrt(1 - (2 * half_x / width) ** 2))
        top += th + gap
    height = math.ceil(required / 4) * 4
    top = (height - block) / 2
    boxes = []
    for tw, th in zip(widths, heights):
        left = (width - tw) / 2
        boxes.append((left, top, left + tw, top + th))
        top += th + gap
    return BalloonSize(variant, width, height, font_size, gap, tuple(boxes))
