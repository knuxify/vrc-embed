# SPDX-License-Identifier: MIT
"""Fetching data from VRChat and caching."""

import json
import redis
import pyotp
import vrchatapi
import time
import pickle
from http.cookiejar import Cookie
from vrchatapi.api import authentication_api, users_api
from vrchatapi.exceptions import UnauthorizedException
from vrchatapi.models.two_factor_auth_code import TwoFactorAuthCode
from vrchatapi.models.two_factor_email_code import TwoFactorEmailCode

from . import config

VRC_CONFIG = vrchatapi.Configuration(
    username=config["vrchat"]["username"], password=config["vrchat"]["password"]
)

vrc_api = vrchatapi.ApiClient(VRC_CONFIG)
vrc_api.user_agent = "vrc-embed/0.0.1 (https://github.com/knuxify/vrc-embed)"

LOGGED_IN = False

#: Cache timeout, in seconds.
CACHE_TIMEOUT: int = 60

#: Properties to include in the cache for VRChat users. All properties used in
#: the templates should be included in this list.
USER_CACHED_PROPERTIES = (
    "profile_pic_override_thumbnail",
    "current_avatar_thumbnail_image_url",
    "user_icon",
    "display_name",
    "username",
    "pronouns",
    "last_activity",
    "state",
    "status",
    "status_description",
)

#: Redis configuration.
r = redis.Redis(
    host=config["redis"]["host"],
    port=config["redis"]["port"],
    password=config["redis"].get("password", None),
    decode_responses=True,
)

#: Redis configuration without decoded responses.
r_bin = redis.Redis(
    host=config["redis"]["host"],
    port=config["redis"]["port"],
    password=config["redis"].get("password", None),
    decode_responses=False,
)


def api_make_cookie(name: str, value: str) -> Cookie:
    """Create a Cookie object for the cookie with the given name and value."""
    return Cookie(
        version=0,
        name=name,
        value=value,
    )


def api_log_in() -> bool:
    """
    Log into the VRChat API using the credentials.

    :returns: True if logging in succeeded, False otherwise.
    """
    auth_api = authentication_api.AuthenticationApi(vrc_api)

    auth_cookie_cached = r_bin.get("vrcembed:cookies:auth")
    twofactorauth_cookie_cached = r_bin.get("vrcembed:cookies:twofactorauth")
    if auth_cookie_cached:
        try:
            auth_cookie = pickle.loads(auth_cookie_cached)
            assert auth_cookie.name == "auth"
            twofactorauth_cookie = pickle.loads(twofactorauth_cookie_cached)
            assert twofactorauth_cookie.name == "twoFactorAuth"
        except (AttributeError, AssertionError, pickle.UnpicklingError):
            pass
        else:
            vrc_api.rest_client.cookie_jar.set_cookie(auth_cookie)
            vrc_api.rest_client.cookie_jar.set_cookie(twofactorauth_cookie)

    try:
        current_user = auth_api.get_current_user()

    except UnauthorizedException as e:
        if e.status == 200:
            if "Email 2 Factor Authentication" in e.reason:
                auth_api.verify2_fa_email_code(
                    two_factor_email_code=TwoFactorEmailCode(input("Email 2FA Code: "))
                )

            elif "2 Factor Authentication" in e.reason:
                if "totp" in config["vrchat"]:
                    totp_code = pyotp.TOTP(
                        config["vrchat"]["totp"].upper().replace(" ", "")
                    ).now()
                    auth_api.verify2_fa(
                        two_factor_auth_code=TwoFactorAuthCode(totp_code)
                    )
                else:
                    auth_api.verify2_fa(
                        two_factor_auth_code=TwoFactorAuthCode(input("2FA Code: "))
                    )

            current_user = auth_api.get_current_user()
        else:
            print("Exception when calling API: %s\n", e)
            return False
    except vrchatapi.ApiException as e:
        print("Exception when calling API: %s\n", e)
        return False

    print("Logged in as:", current_user.display_name)

    # Save login cookie for subsequent runs.
    cookie_jar = vrc_api.rest_client.cookie_jar._cookies["api.vrchat.cloud"]["/"]
    r_bin.set("vrcembed:cookies:auth", pickle.dumps(cookie_jar["auth"]))
    r_bin.set(
        "vrcembed:cookies:twofactorauth", pickle.dumps(cookie_jar["twoFactorAuth"])
    )

    return True


def serialize_user(user: vrchatapi.models.user.User) -> dict:
    """Serialize user data into a dictionary."""
    return dict((k, (getattr(user, k) or "")) for k in USER_CACHED_PROPERTIES)


def get_vrc_user(user_id: str) -> dict | None:
    """
    Fetch information about a VRChat user by their user ID.

    If the information is present in the cache, query it instead.

    :returns: Dictionary with user data if the user was found, None otherwise.
    """
    cache_key = f"vrcembed:users:{user_id}"

    try:
        user_cached = int(r.get(cache_key + ":cachetime") or 0)
    except ValueError:
        user_cached = 0

    if not user_cached or (int(time.time()) - user_cached) > CACHE_TIMEOUT:
        try:
            user_api = users_api.UsersApi(vrc_api)
        except vrchatapi.exceptions.UnauthorizedException:
            api_log_in()
            user_api = users_api.UsersApi(vrc_api)
        try:
            _user = user_api.get_user(user_id)
        except vrchatapi.exceptions.NotFoundException:
            user = None
            r.set(cache_key, "{}")
        else:
            user = serialize_user(_user)
            r.set(cache_key, json.dumps(user))
        r.set(cache_key + ":cachetime", str(int(time.time())))

    else:
        user = json.loads(r.get(cache_key)) or None

    return user
