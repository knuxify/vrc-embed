# SPDX-License-Identifier: MIT
"""Quart app entrypoint."""

import asyncio
import datetime

import timeago
from quart import Quart, make_response, render_template, request, send_from_directory
from quart_tasks import QuartTasks

from . import config
from .button import button_anim, button_static
from .font import FONTS_PATH, text_width
from .opts import OptionsManager
from .render import (
    RENDERS_PATH,
    get_render_filename,
    image_cache,
    render_exists,
    svg2png,
    svg_inline_images,
)
from .vrchat import (
    CACHE_TIMEOUT,
    accept_friend_requests_async,
    api_log_in,
    get_vrc_user,
)

app = Quart(__name__)
app.jinja_env.globals.update(
    text_width=text_width,
    bot_id=config["vrchat"]["userid"],
    bot_username=config["vrchat"]["username"],
)
api_log_in()

tasks = QuartTasks(app)
tasks.add_cron_task(image_cache.prune_dormant, "0 */1 * * *")
tasks.add_cron_task(accept_friend_requests_async, "*/1 * * * *")

#: Valid embed types (templates) and which filetypes they support.
EMBEDS = {
    "large": ("svg", "png"),
    "small": ("svg", "png"),
    "tiny": ("svg", "png"),
    "button-anim": ("gif",),
    "button-static": ("png", "gif"),
}

#: Common configuration options for all embeds.
#: For an explanation of the type system, see OptionsManager in opts.py.
COMMON_OPTS = {
    "inline_img": {"type": ("bool",), "default": "false"},
    "icon_url": {"type": ("url",), "default": ""},
    "pic_url": {"type": ("url",), "default": ""},
    "logo": {"type": ("enum", ["big", "small", "none"]), "default": "small"},
    "background_color": {"type": ("color",), "default": "181B1F"},
    "foreground_color": {"type": ("color",), "default": "F8F9FA"},
    "ingame_only": {"type": ("bool",), "default": "false"},
}

#: Options for each embed type.
EMBED_OPTS = {
    "large": OptionsManager(COMMON_OPTS | {
        "logo_position": {
            "type": ("enum", ["topleft", "datatop", "databottom"]),
            "default": "datatop",
        },
        "width": { "type": ("int", {"min": 1, "max": 2000}), "default": "355" },

        "show_icon": {"type": ("bool",), "default": "true"},
        "lastseen": {"type": ("bool",), "default": "true"},
        "pronouns": {"type": ("bool",), "default": "true"},
    }),
    "small": OptionsManager(COMMON_OPTS | {
        "width": { "type": ("int", {"min": 1, "max": 2000}), "default": "250" },

        "show_icon": {"type": ("bool",), "default": "true"},
        "lastseen": {"type": ("bool",), "default": "true"},
        "pronouns": {"type": ("bool",), "default": "true"},
    }),
    "tiny": OptionsManager(COMMON_OPTS | {
        "width": { "type": ("int", {"min": 1, "max": 2000}), "default": "250" },

        "show_icon": {"type": ("bool",), "default": "true"},
        "lastseen": {"type": ("bool",), "default": "false"},
        "pronouns": {"type": ("bool",), "default": "true"},
    }),
    "button-anim": OptionsManager(COMMON_OPTS),
    "button-static": OptionsManager(COMMON_OPTS),
}  # fmt: skip

#: Defaults for all options, passed to the web UI.
OPT_DEFAULTS = dict((t, EMBED_OPTS[t].get_defaults()) for t in EMBED_OPTS.keys())


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
            opts = EMBED_OPTS[embed_base_type].parse_args(request.args)
        except ValueError as e:
            return {"error": str(e)}, 400

        if config["general"].get("block_custom_pfp_and_banner", False) and (
            "icon_url" in opts or "pic_url" in opts
        ):
            return {"error": "This instance does not allow custom pfp/banner URLs"}

        if config["general"].get("no_render_for_custom_pfp_and_banner") and (
            filetype != "svg" or opts["inline_img"]
        ):
            return {
                "error": "This instance does not allow renders with custom pfp/banner URLs"
            }

        if opts["lastseen"]:
            if user.get("last_activity", ""):
                last_seen_str = timeago.format(
                    datetime.datetime.fromisoformat(user["last_activity"]).replace(
                        tzinfo=datetime.timezone.utc
                    ),
                    datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc),
                )
            else:
                last_seen_str = "N/A"
        else:
            last_seen_str = None

        svg = await render_template(
            f"image_{embed_base_type}.svg",
            user=user,
            last_seen_str=last_seen_str,
            opts=opts,
        )
        if opts["inline_img"]:
            svg = await svg_inline_images(svg.encode("utf-8"))

        if filetype == "svg":
            resp = await make_response(svg)
            resp.headers.set("Content-Type", "image/svg+xml")
            resp.cache_control.max_age = CACHE_TIMEOUT
            resp.cache_control.public = True
            return resp

        elif filetype == "png":
            render_filename = get_render_filename(
                user_id, embed_base_type, opts, filetype
            )
            if user_cached and await render_exists(render_filename):
                return await send_from_directory(RENDERS_PATH, render_filename)

            png = await svg2png(bytes(svg, "utf-8"), render_filename)
            resp = await make_response(png)
            resp.headers.set("Content-Type", "image/png")
            resp.cache_control.max_age = CACHE_TIMEOUT
            resp.cache_control.public = True
            return resp


@app.route("/favicon.ico")
async def favicon():
    """Nulled out favicon for browsers."""
    return "", 404


@app.route("/")
async def index():
    """Index page with configurator."""
    return await render_template(
        "index.html",
        allow_custom_url=not config["general"].get(
            "block_custom_pfp_and_banner", False
        ),
        opt_defaults=OPT_DEFAULTS,
    )


@app.route("/fonts/<font_name>")
async def font(font_name):
    """Serve a font as a TTF."""
    return await send_from_directory(FONTS_PATH, font_name)
