# SPDX-License-Identifier: MIT
"""Parser for custom options based on request arguments."""

from typing import Optional

from werkzeug.datastructures.structures import ImmutableMultiDict


class OptionsManager:
    """Parser for custom options based on request arguments."""

    def __init__(self, options: Optional[dict] = None):
        """Initialize the options manager."""
        if options:
            self.set_options(options)

    def set_options(self, options: dict):
        """Set options from a dictionary contaning options and their type tuples."""
        for opt, data in options.items():
            # Validate type tuple
            try:
                self.type_tuple_is_valid(data["type"])
            except ValueError as e:
                raise ValueError(f"Invalid type tuple for {opt}: {e}") from e

            # Validate default value
            if "default" in data and data["default"] is not None:
                try:
                    self.value_from_type_tuple(data["default"], data["type"])
                except ValueError as e:
                    raise ValueError(f"Invalid default value for {opt}: {e}") from e

        self.options = options

    def parse_args(self, args: ImmutableMultiDict) -> dict:
        """Parse request.args into options."""
        for arg in args.keys():
            if arg not in self.options:
                raise ValueError(f"Unknown option {arg}")

        out = {}
        for opt, data in self.options.items():
            value = args.get(opt, None)
            if value is None:
                value = data.get("default", None)
                if value is None:
                    out[opt] = None
                    continue
            try:
                out[opt] = self.value_from_type_tuple(value, data["type"])
            except ValueError as e:
                raise ValueError(f"Invalid value for {opt}: {e}") from e
        return out

    @classmethod
    def type_tuple_is_valid(cls, tt: tuple):
        """Check whether a type tuple is valid. Returns True if so, raises ValueError otherwise."""
        if not isinstance(tt, tuple):
            raise ValueError("Type tuple must be a tuple")
        if len(tt) != 1 and len(tt) != 2:
            raise ValueError(f"Type tuple {tt} should have 1 or 2 items")
        if not isinstance(tt[0], str):
            raise ValueError("First element of type tuple should be a string")

        ttype = tt[0]
        tparam = tt[1] if len(tt) == 2 else None

        # str: Basic string parameter.
        if ttype == "str":
            if tparam is not None:
                raise ValueError("str type does not accept parameter")

        # int: Basic integer parameter.
        elif ttype == "int":
            if tparam is not None:
                raise ValueError("int type does not accept parameter")

        #: bool: Boolean parameter; accepts values of "true" or "false".
        elif ttype == "bool":
            if tparam is not None:
                raise ValueError("bool type does not accept parameter")

        # url: URL-encoded URL to a file.
        elif ttype == "url":
            if tparam is not None:
                raise ValueError("url type does not accept parameter")

        # enum: Enumerator of possible string values.
        elif ttype == "enum":
            if tparam is None or (
                not isinstance(tparam, list) and not isinstance(tparam, tuple)
            ):
                raise ValueError(
                    "Invalid parameter for enum type; must contain a list or tuple of valid string values"
                )
            for val in tparam:
                if not isinstance(val, str):
                    raise ValueError("enum values must be strings")

        # list: List of values. The type parameter is the type tuple of the values
        #       within the list.
        elif ttype == "list":
            try:
                cls.type_tuple_is_valid(tparam)
            except ValueError as e:
                raise ValueError(f"Invalid type tuple for list: {e}") from e

        else:
            raise ValueError(f'Unknown type "{ttype}"')

    @classmethod
    def value_from_type_tuple(cls, value: str, tt: tuple) -> object:
        """
        Check if a stringified value is valid for the type tuple and get the converted form.

        The type tuple is already assumed to have been validated.
        """

        ttype = tt[0]
        tparam = tt[1] if len(tt) == 2 else None

        if not isinstance(value, str):
            raise ValueError("Input value must be a string")

        if ttype == "str":
            return value

        elif ttype == "int":
            try:
                return int(value)
            except ValueError as e:
                raise ValueError(f"Invalid integer: {value}") from e

        elif ttype == "bool":
            if value.lower() == "true":
                return True
            elif not value or value.lower() == "false":
                return False
            raise ValueError(f"Invalid boolean: {value}")

        elif ttype == "url":
            return value

        elif ttype == "enum":
            if value not in tparam:
                raise ValueError(f"Invalid value {value}, must be one of {tparam}")
            return value

        elif ttype == "list":
            if not value:
                return []
            return [
                cls.value_from_type_tuple(x.strip(), tparam) for x in value.split(",")
            ]
