# vrc-embed

Generate embeddable images for VRChat profiles

## Why?

If you want to show off your current VRChat status on an external website (blog, Carrd, forum signature...), there's no easy official way to do it; even doing API queries requires a proper backend due to CORS limitations, which rules out client-side JS-based embeds.

vrc-embed solves this in a simple way: by generating an embeddable image on the server side, then allowing it to be embedded on another website. Images come in multiple flavors; the raw images are SVGs which can be used for space efficiency and speed, but PNG renders are also available for compatibility.

## Setup

You will need a VRChat account to use for API queries (querying user data is not possible without authentication). You can use your own account for this (you will not show up as online while vrc-embed is running), but if your instance sees a lot of use, it may be safer to create a separate account.

Setting up 2FA is highly recommended, as VRChat often asks for a code during authentication, and vrc-embed can generate these codes automatically when a TOTP secret is configured. See the comment in `config.toml.example` for a guide - notably, **you will need to save the TOTP secret to put in the config**.

### Native

* Install Python, Redis, ImageMagick and rsvg-convert (might be part of librsvg package).
* Enable/start the Redis service.
* Create a new virtualenv with `python3 -m venv venv; activate with `. venv/bin/activate`.
* Install dependencies: `python3 -m pip install -r requirements.txt`
  * For Python 3.10 and lower, install `toml` and `taskgroup`.
* Copy `config.toml.example` to `config.toml`. Adjust as needed.
* Download a copy of the Noto Sans Regular font and place it in `fonts/notosans.ttf`.
* Download a copy of the Noto Sans Bold font and place it in `fonts/notosans-bold.ttf`.
* Run with `./run-prod.sh`.

**Note:** For development, you can use `poetry`. Run `poetry install` to fetch dependencies, then run with `poetry run ./run-dev.sh`.

### Docker

See `docker/README.md` for instructions.
