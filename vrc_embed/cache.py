# SPDX-License-Identifier: MIT
"""Cache handling functions and tasks."""

import json
from typing import Union

import redis

from . import config


class Cache:
    """Class representing Redis cache."""

    def __init__(self):
        """Initialize the Cache object."""

        #: Redis configuration.
        self.cache = redis.Redis(
            host=config["redis"]["host"],
            port=config["redis"]["port"],
            password=config["redis"].get("password", None),
            decode_responses=True,
        )

        #: Redis configuration without decoded responses.
        self.cache_bin = redis.Redis(
            host=config["redis"]["host"],
            port=config["redis"]["port"],
            password=config["redis"].get("password", None),
            decode_responses=False,
        )

        print(self.cache.get("abcdef"))

    def _set(
        self, cache: redis.Redis, key: str, value: Union[str, bytes], timeout: int = 0
    ):
        cache.set(key, value)

        if timeout != 0:
            cache.expire(key, timeout)
        else:
            cache.persist(key)

    def get(self, key: str) -> Union[str, None]:
        """Get element by key, as a string."""
        return self.cache.get(key)

    def set(self, key: str, value: str, timeout: int = 0):
        """Set the element with the given key to the given string value."""
        return self._set(self.cache, key, value, timeout)

    def get_bin(self, key: str) -> Union[bytes, None]:
        """Get element by key, as bytes."""
        return self.cache_bin.get(key)

    def set_bin(self, key: str, value: bytes, timeout: int = 0):
        """Set the element with the given key to the given bytes value."""
        return self._set(self.cache_bin, key, value, timeout)

    def get_json(self, key: str) -> Union[dict, None]:
        """Get deserialized JSON value from the cache."""
        raw = self.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def set_json(self, key: str, value: dict, timeout: int = 0):
        """Set dict serialized to JSON as the cache value for the given key."""
        serialized = json.dumps(value)
        return self.set(key, serialized, timeout)

    def delete(self, key: str):
        """Delete element from the cache."""
        self.cache.delete(key)


#: Global cache access object.
cache = Cache()
