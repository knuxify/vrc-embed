# SPDX-License-Identifier: MIT
"""vrc-embed - Generate SVG/PNG preview of your VRChat profile for embedding on websites."""

import os.path

try:
    import tomllib
except ImportError:
    import toml as tomllib

with open("config.toml", "rb") as config_file:
    config = tomllib.load(config_file)


def get_base_path():
    """Get the vrc-embed base repo clone path."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
