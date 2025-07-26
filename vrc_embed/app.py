# SPDX-License-Identifier: MIT
"""Quart app entrypoint."""

import asyncio
import datetime

import timeago
from quart import Quart, make_response, render_template, request, send_from_directory
from quart_tasks import QuartTasks

from .button import button_anim, button_static
from .opts import OptionsManager
from .render import (
    RENDERS_PATH,
    get_render_filename,
    image_cache,
    render_exists,
    svg2png,
    svg_inline_images,
)
from .utils import text_width
from .vrchat import CACHE_TIMEOUT, api_log_in, get_vrc_user

app = Quart(__name__)
app.jinja_env.globals.update(text_width=text_width)
api_log_in()

tasks = QuartTasks(app)
tasks.add_cron_task(image_cache.prune_dormant, "0 */1 * * *")

#: Valid embed types (templates) and which filetypes they support.
EMBEDS = {
    "large": ("svg", "png"),
    "medium": ("svg", "png"),
    "small": ("svg", "png"),
    "button-anim": ("gif",),
    "button-static": ("png", "gif"),
}

#: Valid configuration options for the embeds and their types.
#: For an explanation of the type system, see OptionsManager in opts.py.
OPTS = {
    "pfp_url": {"type": ("url", None)},
    "banner_url": {"type": ("url", None)},
    "hide": {
        "type": ("list", ("enum", ["lastseen", "pfp", "pronouns"])),
    },
    "logo": {"type": ("enum", ["big", "small", "none"]), "default": "small"},
    "logo_position": {
        "type": ("enum", ["topleft", "datatop", "databottom"]),
        "default": "datatop",
    },
}

options_parser = OptionsManager(OPTS)


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
        try:
            opts = options_parser.parse_args(request.args)
        except ValueError as e:
            return {"error": str(e)}, 400

        if "lastseen" not in opts["hide"]:
            last_seen_str = timeago.format(
                datetime.datetime.fromisoformat(user["last_activity"]).replace(
                    tzinfo=datetime.timezone.utc
                ),
                datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc),
            )
        else:
            last_seen_str = None

        svg = await render_template(
            f"image_{embed_base_type}.svg",
            user=user,
            last_seen_str=last_seen_str,
            opts=opts,
        )
        if request.args.get("inlineimg", "false") == "true":
            svg = await svg_inline_images(svg.encode("utf-8"))

        if filetype == "svg":
            resp = await make_response(svg)
            resp.headers.set("Content-Type", "image/svg+xml")
            resp.headers.set("Cache-Control", f"maxage={CACHE_TIMEOUT}")
            return resp

        elif filetype == "png":
            render_filename = get_render_filename(user_id, embed_base_type, filetype)
            if user_cached and await render_exists(render_filename):
                return await send_from_directory(RENDERS_PATH, render_filename)

            png = await svg2png(bytes(svg, "utf-8"), render_filename)
            resp = await make_response(png)
            resp.headers.set("Content-Type", "image/png")
            resp.headers.set("Cache-Control", f"maxage={CACHE_TIMEOUT}")
            return resp


@app.route("/favicon.ico")
async def favicon():
    """Nulled out favicon for browsers."""
    return "", 404


@app.route("/")
async def index():
    """Index page with configurator."""
    return await render_template("index.html")
