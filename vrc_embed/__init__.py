# SPDX-License-Identifier: MIT
"""vrc-embed - Generate SVG/PNG preview of your VRChat profile for embedding on websites."""

try:
    import tomllib
except ImportError:
    import toml as tomllib

with open("config.toml", "rb") as config_file:
    config = tomllib.load(config_file)
