# SPDX-License-Identifier: MIT
"""Miscelaneous functions."""

import os.path

from PIL import ImageFont

from . import config, get_base_path

#: Loaded font cache for text_width().
_font_cache = {}

#: Font name to font file mapping.
FONTS = {"Noto Sans": "notosans.ttf"}

FONTS_PATH = config["general"].get("fonts_path", os.path.join(get_base_path(), "fonts"))


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

        font_path = os.path.join(FONTS_PATH, FONTS[font_name])

        try:
            font = ImageFont.truetype(font_path, size=size)
        except OSError as e:
            raise Exception(
                f"Missing font file for {font_name}; tried to look in {font_path}"
            ) from e

        _font_cache[font_key] = font

    return font.getlength(text)
