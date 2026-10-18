"""bernstein's settings: ~/.bernstein.conf, then the command line, which wins."""

import argparse
import re
from types import SimpleNamespace

from bernstein.names import NameRefused, check_name


class SettingsRefused(ValueError):
    """A setting or argument cannot be used; the message says which and why."""


EFFORTS = ("low", "medium", "high", "xhigh", "max")

DEFAULTS = {
    "TEMPLATE": "~/projects/code/bernstein-code/templates/lobster",
    "NON_CODE_DIR": "~/projects/non-code",
    "CODE_DIR": "~/projects/code",
    "MODEL": "opus",
    "EFFORT": "high",
    "LOBSTER_MAIL": "~/projects/code/lobster-tools-code/lobster-tools/lobster-mail",
    "MAIL_ROOT": "~/projects/mail",
    "PYTHON": "/usr/bin/python3",
}

PATHS = ("TEMPLATE", "NON_CODE_DIR", "CODE_DIR", "LOBSTER_MAIL", "MAIL_ROOT", "PYTHON")


def expand(value, home):
    """A leading ~ means the home folder."""
    if value == "~" or value.startswith("~/"):
        return home + value[1:]
    return value


def unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def check_effort(effort, where):
    if effort not in EFFORTS:
        raise SettingsRefused("{} must be one of {}".format(where, ", ".join(EFFORTS)))


def check_model(model, where):
    if model == "":
        raise SettingsRefused(f"{where} is empty")
    if not re.fullmatch(r"[A-Za-z0-9.-]+", model):
        raise SettingsRefused(f"{where} must be one word, such as opus or sonnet")


def read_settings(text, home):
    """The settings from a ~/.bernstein.conf text, over the defaults, with ~ filled in."""
    found = dict(DEFAULTS)
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise SettingsRefused(f"line {number}: not a KEY=value line: {stripped}")
        key, value = (part.strip() for part in stripped.split("=", 1))
        if key not in DEFAULTS:
            raise SettingsRefused(f"line {number}: unknown setting {key}")
        value = unquote(value)
        if key == "EFFORT":
            check_effort(value, f"line {number}: EFFORT")
        if key == "MODEL":
            check_model(value, f"line {number}: MODEL")
        found[key] = value
    for key in PATHS:
        found[key] = expand(found[key], home)
    return found


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SettingsRefused(message)


def parser_for_new_lobster():
    p = Parser(
        prog="new-lobster",
        description="Make a new lobster project: a non-code project and its tools project, "
        "with a mailbox each, from bernstein's lobster-project template.",
    )
    p.add_argument("name", help="the non-code project's name; the tools project is <name>-tools")
    p.add_argument("--dry-run", action="store_true", help="check and show everything, write nothing")
    p.add_argument("--public", action="store_true", help="make the tools project public (default private)")
    p.add_argument("--template", metavar="DIR", help="the lobster-project template (setting TEMPLATE)")
    p.add_argument("--non-code-dir", metavar="DIR", help="where non-code projects go (setting NON_CODE_DIR)")
    p.add_argument("--code-dir", metavar="DIR", help="where code projects go (setting CODE_DIR)")
    p.add_argument("--model", help="the model sessions must run on (setting MODEL)")
    p.add_argument("--effort", help="the effort sessions must run at (setting EFFORT)")
    p.add_argument("--render-into", metavar="DIR", help="only render the template for the pair into DIR, "
                   "a new folder, for bringing an existing pair into line; make nothing else")
    p.add_argument("--tools", metavar="NAME", help="with --render-into: the tools project's name (default <name>-tools)")
    p.add_argument("--non-code-path", metavar="DIR", help="with --render-into: where the non-code project is")
    p.add_argument("--tools-path", metavar="DIR", help="with --render-into: where the tools checkout is")
    return p


def options_for_new_lobster(argv, settings):
    """The options for one run of new-lobster: the flags over the settings."""
    a = parser_for_new_lobster().parse_args(argv)
    try:
        check_name(a.name)
    except NameRefused as why:
        raise SettingsRefused(f"the name {a.name} cannot be used: {why}")
    for flag, value in (("--tools", a.tools), ("--non-code-path", a.non_code_path), ("--tools-path", a.tools_path)):
        if value is not None and a.render_into is None:
            raise SettingsRefused(f"{flag} needs --render-into")
    if a.tools is not None:
        if not a.tools.endswith("-tools"):
            raise SettingsRefused(f"the tools name {a.tools} must end in -tools")
        try:
            check_name(a.tools[: -len("-tools")])
        except NameRefused as why:
            raise SettingsRefused(f"the tools name {a.tools} cannot be used: {why}")
    if a.effort is not None:
        check_effort(a.effort, "--effort")
    if a.model is not None:
        check_model(a.model, "--model")
    return SimpleNamespace(
        name=a.name,
        dry_run=a.dry_run,
        public=a.public,
        template=a.template or settings["TEMPLATE"],
        non_code_dir=a.non_code_dir or settings["NON_CODE_DIR"],
        code_dir=a.code_dir or settings["CODE_DIR"],
        model=a.model or settings["MODEL"],
        effort=a.effort or settings["EFFORT"],
        lobster_mail=settings["LOBSTER_MAIL"],
        mail_root=settings["MAIL_ROOT"],
        python=settings["PYTHON"],
        render_into=a.render_into,
        tools=a.tools,
        non_code_path=a.non_code_path,
        tools_path=a.tools_path,
    )
