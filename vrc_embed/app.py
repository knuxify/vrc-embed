# SPDX-License-Identifier: MIT
"""Quart app entrypoint."""

import asyncio
import datetime

import timeago
from quart import Quart, make_response, render_template, send_from_directory

from .button import button_anim, button_static
from .render import RENDERS_PATH, get_render_filename, render_exists, svg2png
from .utils import text_width
from .vrchat import api_log_in, get_vrc_user

app = Quart(__name__)
app.jinja_env.globals.update(text_width=text_width)
api_log_in()


#: Valid embed types (templates) and which filetypes they support.
EMBEDS = {
    "large": ("svg", "png"),
    "medium": ("svg", "png"),
    "small": ("svg", "png"),
    "button-anim": ("gif",),
    "button-static": ("png", "gif"),
}


@app.route("/<user_id>/<embed_type>")
async def get_user_embed(user_id: str, embed_type: str):
    """Get embed for the user with the given ID."""
    embed_base_type = embed_type.split(".")[0]
    if embed_base_type not in EMBEDS or embed_type not in (
        embed_base_type + "." + x for x in EMBEDS[embed_base_type]
    ):
        return {"error": "Invalid embed type"}, 404
    filetype = embed_type.split(".")[1]

    user, user_cached = await asyncio.to_thread(get_vrc_user, user_id)

    if not user:
        return {"error": "User not found"}, 404

    # 88x31 buttons are generated with custom code
    if embed_base_type == "button-anim":
        return await asyncio.to_thread(button_anim(filetype, user))

    elif embed_base_type == "button-static":
        return await asyncio.to_thread(button_static(filetype, user))

    else:
        last_seen_str = timeago.format(
            datetime.datetime.fromisoformat(user["last_activity"]).replace(
                tzinfo=datetime.timezone.utc
            ),
            datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc),
        )

        svg = await render_template(
            f"image_{embed_base_type}.svg", user=user, last_seen_str=last_seen_str
        )

        if filetype == "svg":
            resp = await make_response(svg)
            resp.headers.set("Content-Type", "image/svg")
            return resp

        elif filetype == "png":
            render_filename = get_render_filename(user_id, embed_base_type, filetype)
            if user_cached and await render_exists(render_filename):
                return await send_from_directory(RENDERS_PATH, render_filename)

            png = await svg2png(bytes(svg, "utf-8"), render_filename)
            resp = await make_response(png)
            resp.headers.set("Content-Type", "image/png")
            return resp


@app.route("/favicon.ico")
async def favicon():
    """Nulled out favicon for browsers."""
    return "", 404


@app.route("/")
async def index():
    """Index page with configurator."""
    return await render_template("index.html")
