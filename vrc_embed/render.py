# SPDX-License-Identifier: MIT
"""Code for dealing with rendered files and rendering SVG to PNG."""

import asyncio
import base64
import os.path
import xml.etree.ElementTree as ET
from typing import Optional

import aiofiles
import aiofiles.os
import aiohttp
from wand.color import Color
from wand.image import Image

try:
    from asyncio import TaskGroup
except AttributeError:
    from taskgroup import TaskGroup

from . import config
from .utils import get_base_path

#: Base directory used for renders.
RENDERS_PATH = config["general"].get(
    "renders_path", os.path.join(get_base_path(), "renders")
)


def get_render_filename(user_id: str, embed_base_type: str, filetype: str) -> str:
    """
    Get the render filename for the given parameters.

    Note that this only contains the filename, not the renders directory.
    """
    return user_id + "." + embed_base_type + "." + filetype


async def save_render(filename: str, data: bytes):
    """Save a rendered image to the renders directory with the given filename."""

    # Write to temporary file to avoid serving half-finished render
    async with aiofiles.open(os.path.join(RENDERS_PATH, "." + filename), "wb") as f:
        await f.write(data)

    # Move temporary file to main location
    await aiofiles.os.replace(
        os.path.join(RENDERS_PATH, "." + filename), os.path.join(RENDERS_PATH, filename)
    )


async def render_exists(filename: str) -> bool:
    """Check if the render with the given filename exists."""
    return await aiofiles.os.path.exists(os.path.join(RENDERS_PATH, filename))


async def svg_inline_images(source: bytes) -> bytes:
    """
    Download images in the SVG and inline them as data blobs into the SVG.

    Most SVG renderers cannot fetch external images themselves; as such,
    we need to perform the inlining here.
    """
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    source_str = source.decode("utf-8")
    source_el = ET.fromstring(source_str)

    # Find all <image> tags and check if they have valid href values
    images = []
    for img in source_el.iter():
        if not img.tag.endswith("image"):
            continue

        if "href" in img.attrib and (
            img.attrib["href"].startswith("https://")
            or img.attrib["href"].startswith("http://")
            or img.attrib["href"].startswith("//")
        ):
            images.append(img)

    # If there are no valid tags, we have nothing to do
    if not images:
        return source

    # Common function for performing the inline action on an <image> element:
    async def _inline_image(img):
        # Download the image file
        headers = {
            "User-Agent": "vrc-embed/0.0.1 (https://github.com/knuxify/vrc-embed)"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(img.attrib["href"], headers=headers) as response:
                data = await response.read()

        # Base64-encode the image data and replace href attribute
        b64 = await asyncio.to_thread(base64.b64encode, data)
        b64_str = await asyncio.to_thread(b64.decode, "ascii")
        img.attrib["href"] = "data:image/png;base64," + b64_str

    # Run the above function in a taskgroup so that multiple files can be downloaded
    # at once.
    _tasks = set()
    async with TaskGroup() as tg:
        for img in images:
            _tasks.add(tg.create_task(_inline_image(img)))

    # Turn the modified element tree back into bytes and return the result
    return ET.tostring(source_el, encoding="utf-8")


def _wand_svg2png(source: bytes) -> bytes:
    with Image() as img:
        img.background_color = Color("transparent")
        img.read(blob=source, format="svg", depth=8)
        img.options["png:compression-level"] = "9"
        return img.make_blob("png")


async def svg2png(source: bytes, filename: Optional[str] = None) -> bytes:
    """
    Convert an SVG file (provided as bytes) to a PNG (returned as bytes).

    With the write_path parameter, will also create a background task to write
    the file.
    """

    # Get the SVG with all images inlined
    source = await svg_inline_images(source)

    # Send a call to wand/ImageMagick to process the image
    out = await asyncio.to_thread(_wand_svg2png, source)

    # Start a task to save the resulting render in the background
    if filename is not None:
        asyncio.create_task(save_render(filename, out))

    return out
