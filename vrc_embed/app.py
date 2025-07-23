# SPDX-License-Identifier: MIT
"""
Quart app entrypoint.
"""

import asyncio
import datetime
import timeago
from quart import Quart, render_template

from .utils import text_width
from .vrchat import api_log_in, get_vrc_user

app = Quart(__name__)
app.jinja_env.globals.update(text_width=text_width)
api_log_in()


@app.route("/favicon.ico")
def favicon():
    return "", 404


@app.route("/<user_id>")
async def get_user_embed(user_id: str):
    """Get embed for the user with the given ID."""
    user = await asyncio.to_thread(get_vrc_user, user_id)

    if not user:
        return "", 404

    last_seen_str = timeago.format(
        datetime.datetime.fromisoformat(user["last_activity"]).replace(
            tzinfo=datetime.timezone.utc
        ),
        datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc),
    )

    return await render_template(
        "image_large.svg", user=user, last_seen_str=last_seen_str
    )
