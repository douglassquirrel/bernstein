"""conform: list what an existing lobster pair lacks against bernstein's template. Read-only.

PLAN.md (Settled 55) is the specification. Exit codes: 0 nothing missing, 1 something missing,
2 bad arguments or settings, 4 the template cannot be read.
"""

import argparse
import datetime
import os

from bernstein.conduct import (
    ProjectRefused,
    locate,
    non_code_folder_in,
    read_conf_file,
    tools_folders_in,
)
from bernstein.newlobster import OUTER_FILES, OUTER_FOLDERS
from bernstein.render import INCLUDE, PLACEHOLDER, TemplateRefused, fill, values_for
from bernstein.settings import SettingsRefused, read_settings

# A template heading with one of these names the pair, so every pair's CLAUDE.md must have it.
PAIR_NAMES = {"NAME", "TOOLS", "SELF", "SISTER"}


def find(name, kind, s):
    """(folder, checkout) for one half, or None."""
    if kind == "code":
        return locate(name, s["CODE_DIR"], tools_folders_in)
    folder = locate(name, s["NON_CODE_DIR"], non_code_folder_in)
    return (folder, folder) if folder else None


def conf_gaps(conf, wanted):
    """What lobster.conf lacks: the right KIND, SELF and SISTER, and a MODEL and an EFFORT."""
    try:
        settings = read_conf_file(conf)
    except (UnicodeDecodeError, OSError):
        return ["lobster.conf as plain UTF-8 text"]
    gaps = []
    for key, value in wanted.items():
        if settings.get(key) != value:
            said = f" (it says {settings[key]})" if settings.get(key) else ""
            gaps.append(f"{key}={value} in lobster.conf{said}")
    gaps += [f"{key} in lobster.conf" for key in ("MODEL", "EFFORT") if not settings.get(key)]
    return gaps


def required_headings(s, kind, non_code, tools, public, home):
    """The headings a half's CLAUDE.md must have: every heading of each section the template's CLAUDE.md
    for that half includes from common/sections/, and every heading of its own that names the pair."""
    values = values_for(non_code, kind, model=s["MODEL"], effort=s["EFFORT"], non_code_dir=s["NON_CODE_DIR"],
                        code_dir=s["CODE_DIR"], mail_root=s["MAIL_ROOT"], lobster_mail=s["LOBSTER_MAIL"],
                        public=public, today=datetime.date.today(), home=home, tools=tools)
    where = f"{kind}/CLAUDE.md"
    with open(os.path.join(s["TEMPLATE"], kind, "CLAUDE.md"), encoding="utf-8") as f:
        raw = f.read()
    headings = []
    for line in raw.splitlines():
        include = INCLUDE.fullmatch(line)
        if include:
            section = os.path.join(s["TEMPLATE"], "common", fill(include.group(1), values, where))
            with open(section, encoding="utf-8") as f:
                headings += [fill(h, values, section) for h in f.read().splitlines() if h.startswith("## ")]
        elif line.startswith("## ") and set(PLACEHOLDER.findall(line)) & PAIR_NAMES:
            headings.append(fill(line, values, where))
    return headings


def claude_gaps(folder, headings):
    claude = os.path.join(folder, "CLAUDE.md")
    if not os.path.isfile(claude):
        return ["CLAUDE.md"]
    with open(claude, encoding="utf-8", errors="replace") as f:
        have = set(f.read().splitlines())
    return [f'the section "{h}" in CLAUDE.md' for h in headings if h not in have]


def gaps_of(name, kind, sister, found, s):
    """What one half lacks, as lines."""
    folder, _checkout = found
    gaps = []
    conf = os.path.join(folder, "lobster.conf")
    if not os.path.isfile(conf):
        gaps.append("lobster.conf")
    else:
        gaps += conf_gaps(conf, {"KIND": kind, "SELF": name, "SISTER": sister})
    if not os.path.isfile(os.path.join(folder, "START-HERE.txt")):
        gaps.append("START-HERE.txt")
    hook = os.path.join(folder, ".claude", "settings.json")
    if not os.path.isfile(hook):
        gaps.append(".claude/settings.json (the lobster-mail start hook)")
    else:
        with open(hook, encoding="utf-8", errors="replace") as f:
            text = f.read()
        if "lobster-mail" not in text or " start --project" not in text.replace('\\"', ""):
            gaps.append("the lobster-mail start hook in .claude/settings.json")
    if not os.path.isfile(os.path.join(folder, "inbox", "README.md")):
        gaps.append("inbox/README.md")
    non_code, tools = (name, sister) if kind == "non-code" else (sister, name)
    gaps += claude_gaps(folder, required_headings(s, kind, non_code, tools, found[0] != found[1], s["HOME"]))
    checkout = found[1]
    if checkout != folder:
        for rel in OUTER_FILES + OUTER_FOLDERS:
            if os.path.lexists(os.path.join(checkout, rel.rstrip("/"))):
                gaps.append(f"{rel} beside the checkout, not in it ({checkout})")
    if not os.path.isdir(os.path.join(checkout, ".git")):
        gaps.append(f"a git repository in {checkout}")
    if not os.path.isdir(os.path.join(folder, "backlog")):
        gaps.append(f"backlog/ in {folder}")
    if not os.path.isdir(os.path.join(s["MAIL_ROOT"], name)):
        gaps.append(f"the mailbox {name} in {s['MAIL_ROOT']}")
    return gaps


class Stop(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Stop(2, f"{message} (conform --help shows the form)")


def parser():
    p = Parser(prog="conform", description="List what an existing lobster pair lacks against bernstein's "
               "lobster-project template. Reads only; changes nothing.")
    p.add_argument("non_code", help="the non-code project's name")
    p.add_argument("tools", help="the tools project's name")
    return p


def report(a, s, out):
    """Write the report; return the number of things missing."""
    total = 0
    for name, kind, sister in ((a.non_code, "non-code", a.tools), (a.tools, "code", a.non_code)):
        base = s["CODE_DIR"] if kind == "code" else s["NON_CODE_DIR"]
        try:
            found = find(name, kind, s)
            why = f"{name} is not in {base} or a folder directly inside it"
        except ProjectRefused as refused:
            found, why = None, str(refused)
        if found is None:
            out.write(f"{name} ({kind}): not found\n  {why}\n")
            total += 1
            continue
        out.write(f"{name} ({kind}): {found[0]}\n")
        try:
            gaps = gaps_of(name, kind, sister, found, s)
        except (TemplateRefused, OSError) as why:
            raise Stop(4, f"the template cannot be read: {why}")
        out.write("".join(f"  missing: {g}\n" for g in gaps) or "  in line\n")
        total += len(gaps)
    return total


def main(argv, env, out, err):
    """Run conform; return its exit code."""
    if argv[:1] in (["-h"], ["--help"]):
        out.write(parser().format_help())
        return 0
    try:
        path = env.get("BERNSTEIN_CONF") or os.path.join(env["HOME"], ".bernstein.conf")
        text = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                text = f.read()
        try:
            s = read_settings(text, env["HOME"])
        except SettingsRefused as why:
            raise Stop(2, f"{path}: {why}")
        s["HOME"] = env["HOME"]
        total = report(parser().parse_args(argv), s, out)
    except Stop as stopped:
        err.write(f"conform: {stopped.message}\n")
        return stopped.code
    if total:
        out.write(f"{total} thing{'s' if total != 1 else ''} to bring into line.\n")
        return 1
    out.write("Both halves are in line.\n")
    return 0
