# SPDX-License-Identifier: MIT

try:
    import tomllib
except ImportError:
    import toml as tomllib

with open("config.toml", "rb") as config_file:
    config = tomllib.load(config_file)
