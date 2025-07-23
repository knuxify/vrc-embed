# SPDX-License-Identifier: MIT
"""
Miscelaneous functions.
"""

from PIL import ImageFont
import os.path

from . import config

#: Loaded font cache for text_width().
_font_cache = {}

#: Font name to font file mapping.
FONTS = {"Noto Sans": "notosans.ttf"}

FONTS_DIR = config.get("fonts", {}).get(
    "path",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts"),
)


def text_width(text: str, font_name: str, size: float) -> float:
    """
    Get the estimated length in pixels of the given text for the font.

    :param text: Text to estimate the length of.
    :param font_name: Name of the font to use for estimations.
    :raises ValueError: If the font with the given name is not available.
    """
    global _font_cache
    font_key = f"{font_name}-{size}"

    if font_key in _font_cache:
        font = _font_cache[font_key]
    else:
        if font_name not in FONTS:
            raise ValueError(f"Font {font_name} not available")
        font = ImageFont.truetype(os.path.join(FONTS_DIR, FONTS[font_name]), size=size)
        _font_cache[font_key] = font

    return font.getlength(text)
