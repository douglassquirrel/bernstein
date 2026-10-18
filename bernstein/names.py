"""Checking a lobster project's name."""

import re


class NameRefused(ValueError):
    """The name cannot be used; the message says why."""


def check_name(name):
    """Return None if `name` can be a lobster project's name; raise NameRefused saying why if not."""
    if name == "":
        raise NameRefused("the name is empty")
    if not re.fullmatch(r"[a-z0-9-]+", name):
        raise NameRefused("use only lower-case letters, digits and hyphens")
    if not 2 <= len(name) <= 40:
        raise NameRefused("the name must be 2 to 40 characters long")
    if not name[0].isalpha():
        raise NameRefused("the name must start with a letter")
    if name.endswith("-"):
        raise NameRefused("the name must not end with a hyphen")
    if "--" in name:
        raise NameRefused("use single hyphens only")
    if name.endswith("-tools"):
        raise NameRefused("the name must not end in -tools: new-lobster adds -tools for the tools project")
    return None
