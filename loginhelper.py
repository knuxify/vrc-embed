# SPDX-License-Identifier: MIT
"""
Helper script which runs the VRChat login procedure; helpful when e.g. prior email
verification is needed.
"""

from vrc_embed.vrchat import api_log_in

if __name__ == "__main__":
    api_log_in()
