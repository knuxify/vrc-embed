# vrc-embed dockerfile.
# NOTE: This file expects the build context to be set to the vrc-embed source code directory.

ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-alpine as base

# ...configurable args start here...

# The default listening port is 7878. If you need to use a different
# port, change the line below.
ENV VRC_EMBED_PORT=7878

# By default, hypercorn is configured to start 4 workers. If you want to
# change this, change the line below.
ENV VRC_EMBED_WORKERS=4

# ...configurable args end here...


# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

WORKDIR /opt/vrc-embed

# Copy the source code into the container
COPY . .

# Download ImageMagick, rsvg-convert and Noto fonts
RUN apk update
RUN apk add imagemagick imagemagick-svg rsvg-convert font-noto shadow runuser
RUN cp /usr/share/fonts/noto/NotoSans-Regular.ttf ./fonts/notosans.ttf
RUN cp /usr/share/fonts/noto/NotoSans-Bold.ttf ./fonts/notosans-bold.ttf

# Wand bug: it can't find the so.XX libraries, so manual
# symlinks need to be made.
RUN ln -s /usr/lib/libMagickCore-7.Q16HDRI.so.*.* /usr/lib/libMagickCore-7.Q16HDRI.so
RUN ln -s /usr/lib/libMagickWand-7.Q16HDRI.so.*.* /usr/lib/libMagickWand-7.Q16HDRI.so

# Install vrc-embed dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install .

# Add vrc-embed user
ARG UID=10001
ARG GID=10001
RUN groupadd -g "${GID}" vrc-embed
RUN useradd -m -u ${UID} -g vrc-embed vrc-embed

# Expose the listening port
EXPOSE ${VRC_EMBED_PORT}

# Run the main vrc-embed server
CMD docker/run-app-docker.sh "$VRC_EMBED_PORT" "$VRC_EMBED_WORKERS"
