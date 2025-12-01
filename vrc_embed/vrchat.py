# SPDX-License-Identifier: MIT
"""Fetching data from VRChat and caching."""

import json
import pickle
from http.cookiejar import Cookie
from typing import Tuple, Union

import pyotp
import vrchatapi
from vrchatapi.api import authentication_api, friends_api, notifications_api, users_api
from vrchatapi.exceptions import UnauthorizedException
from vrchatapi.models.notification_type import NotificationType
from vrchatapi.models.two_factor_auth_code import TwoFactorAuthCode
from vrchatapi.models.two_factor_email_code import TwoFactorEmailCode

from . import config
from .cache import cache

VRC_CONFIG = vrchatapi.Configuration(
    username=config["vrchat"]["username"], password=config["vrchat"]["password"]
)

vrc_api = vrchatapi.ApiClient(VRC_CONFIG)
vrc_api.user_agent = "vrc-embed/0.0.1 (https://github.com/knuxify/vrc-embed)"

LOGGED_IN = False

#: Cache timeout, in seconds.
CACHE_TIMEOUT: int = config["vrchat"].get("cache_timeout", 60)

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

    auth_cookie_cached = cache.get_bin("vrcembed:cookies:auth")
    twofactorauth_cookie_cached = cache.get_bin("vrcembed:cookies:twofactorauth")
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
        try:
            json_body = json.loads(e.body)
        except ValueError:
            json_body = None

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

        elif (
            e.status == 401
            and json_body
            and "email"
            in json_body.get("error", {"message": ""}).get("message", "").lower()
        ):
            # E-mail verification prompt
            auth_api.verify_login_place(
                token=input(
                    "Open your e-mail and click on the verification link, or copy the token= field from the URL: "
                ).strip(),
                user_id=config["vrchat"]["userid"],
            )
            current_user = auth_api.get_current_user()

        else:
            print("UnauthorizedException when calling API: %s\n", e, e.reason)
            return False
    except vrchatapi.ApiException as e:
        try:
            json_body = json.loads(e.body)
        except ValueError:
            json_body = None

        if (
            e.status == 429
            and json_body
            and "email"
            in json_body.get("error", {"message": ""}).get("message", "").lower()
        ):
            print(
                "WARNING: E-mail verification was attempted too many times and is now returning 429. If clicking the link doesn't work, try again later."
            )
            # E-mail verification prompt
            auth_api.verify_login_place(
                token=input(
                    "Open your e-mail and click on the verification link, or copy the token= field from the URL: "
                ).strip(),
                user_id=config["vrchat"]["userid"],
            )
            current_user = auth_api.get_current_user()
        else:
            print("Exception when calling API: %s\n", e, e.reason)
            return False

    print("Logged in as:", current_user.display_name)

    # Save login cookie for subsequent runs.
    cookie_jar = vrc_api.rest_client.cookie_jar._cookies["api.vrchat.cloud"]["/"]
    cache.set_bin("vrcembed:cookies:auth", pickle.dumps(cookie_jar["auth"]))
    cache.set_bin(
        "vrcembed:cookies:twofactorauth", pickle.dumps(cookie_jar["twoFactorAuth"])
    )

    return True


def serialize_user(user: vrchatapi.models.user.User) -> dict:
    """Serialize user data into a dictionary."""
    out = dict((k, (getattr(user, k) or "")) for k in USER_CACHED_PROPERTIES)

    # Manually add the user icon thumbnail field
    if out["user_icon"]:
        out["user_icon_thumbnail"] = (
            out["user_icon"].replace("/api/1/file", "/api/1/image") + "/128"
        )

    return out


def get_vrc_user(user_id: str) -> Tuple[Union[dict, None], bool]:
    """
    Fetch information about a VRChat user by their user ID.

    If the information is present in the cache, query it instead.

    :returns: Tuple with two items:
      - Dictionary with user data if the user was found, None otherwise.
      - Boolean representing cache hit; True if response was cached, False otherwise.
    """
    cache_key = f"vrcembed:users:{user_id}"
    user = cache.get_json(cache_key)
    user_cached = True

    if not user:
        user_cached = False
        user_api = users_api.UsersApi(vrc_api)

        try:
            _user = user_api.get_user(user_id)
        except vrchatapi.exceptions.UnauthorizedException:
            api_log_in()
            _user = user_api.get_user(user_id)
        except vrchatapi.exceptions.NotFoundException:
            user = None
            cache.set(cache_key, "{}", timeout=CACHE_TIMEOUT)
        else:
            user = serialize_user(_user)
            cache.set_json(cache_key, user, timeout=CACHE_TIMEOUT)

    return (user, user_cached)


def accept_friend_requests():
    """Go through all friend requests and accept them."""
    notif_api = notifications_api.NotificationsApi(vrc_api)
    friend_api = friends_api.FriendsApi(vrc_api)

    notifs = notif_api.get_notifications(type=NotificationType.FRIENDREQUEST)
    for notif in notifs:
        try:
            # Accept the friend request using the sender's user ID
            friend_api.friend(user_id=notif.sender_user_id)
            notif_api.delete_notification(notif.id)
        except Exception as e:
            print(f"Error accepting friend request from {notif}: {e}")


async def accept_friend_requests_async():
    """Async wrapper around accept_friend_requests for Quart-Tasks."""
    accept_friend_requests()
