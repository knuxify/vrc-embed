# SPDX-License-Identifier: MIT
"""Code for dealing with rendered files and rendering SVG to PNG."""

import asyncio
import atexit
import base64
import hashlib
import json
import os.path
import tempfile
import time
import xml.etree.ElementTree as ET
from typing import Optional

import aiofiles
import aiofiles.os
import aiohttp
import filetype
import json_fingerprint
from filetype.types import IMAGE as image_matchers
from wand.color import Color
from wand.image import Image

try:
    from asyncio import TaskGroup
except AttributeError:
    from taskgroup import TaskGroup

from . import config, get_base_path

#: Base directory used for renders.
RENDERS_PATH = config["general"].get(
    "renders_path", os.path.join(get_base_path(), "renders")
)


class ImageCache:
    """Image file cache manager."""

    def __init__(self):
        """Initialize the image cache manager."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = self.tmpdir.name

        #: Last cache hit for each stored image.
        self.last_hit = {}

        #: List of files which are currently being downloaded.
        self.download_queue = set()

    def close_tmpdir(self):
        """
        Close the temporary directory.

        After calling this, the ImageCache object should no longer be used.
        """
        self.tmpdir.cleanup()
        del self.last_hit

    async def get(self, url: str) -> bytes:
        """Download an image or fetch it from the cache."""
        url_hash = await asyncio.to_thread(
            lambda url: hashlib.sha512(url.encode("utf-8")).hexdigest(), url
        )
        self.last_hit[url_hash] = time.time()

        path = os.path.join(self.path, url_hash)

        # If the URL is currently being downloaded, wait until that download finishes
        while url in self.download_queue:
            await asyncio.sleep(0.05)
        self.download_queue.add(url)

        # If we have a cached file, serve it
        if await aiofiles.os.path.exists(path):
            self.download_queue.remove(url)
            async with aiofiles.open(path, "rb") as f:
                return await f.read()

        # Otherwise, download the image file and save it to the cache
        else:
            ret = bytes()
            headers = {
                "User-Agent": "vrc-embed/0.0.1 (https://github.com/knuxify/vrc-embed)"
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        async with aiofiles.open(path, "wb") as f:
                            async for chunk in response.content.iter_chunked(4096):
                                await f.write(chunk)
                                ret += chunk
            except:  # noqa: E722
                ret = None

            self.download_queue.remove(url)

            return ret

    async def prune_dormant(self):
        """Prune unused images that haven't been used in a while."""
        now = time.time()
        for url_hash, last_hit in list(self.last_hit.items()).copy():
            if (now - last_hit) > (60 * 60 * 12):
                del self.last_hit[url_hash]
                await aiofiles.os.remove(os.path.join(self.path, url_hash))


#: Image cache handler.
image_cache = ImageCache()
atexit.register(image_cache.close_tmpdir)


def get_render_filename(
    user_id: str, embed_base_type: str, opts: dict, filetype: str
) -> str:
    """
    Get the render filename for the given parameters.

    Note that this only contains the filename, not the renders directory.
    """
    if opts:
        fp = json_fingerprint.create(
            json.dumps(opts), json_fingerprint.hash_functions.SHA256, 1
        ).split("$")[2]
        return user_id + "." + embed_base_type + "." + fp + "." + filetype
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
        data = await image_cache.get(img.attrib["href"])

        # Base64-encode the image data and replace href attribute
        b64 = await asyncio.to_thread(base64.b64encode, data)
        b64_str = await asyncio.to_thread(b64.decode, "ascii")
        mimetype = filetype.match(data, matchers=image_matchers)
        if mimetype:
            img.attrib["href"] = f"data:{mimetype.mime};base64," + b64_str
        else:
            img.attrib["href"] = "data:base64," + b64_str

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
