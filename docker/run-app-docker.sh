#!/bin/sh

[ ! "$VRC_EMBED_WORKERS" ] && export VRC_EMBED_WORKERS=$2
[ ! "$VRC_EMBED_PORT" ] && export VRC_EMBED_PORT=$1

export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
export MAGICK_HOME=/usr

chown -R vrc-embed:vrc-embed /opt/vrc-embed/renders

runuser -u vrc-embed -- hypercorn -w "${VRC_EMBED_WORKERS}" "vrc_embed.app" -b 0.0.0.0:"${VRC_EMBED_PORT}"
exit $?
