"""conform: list what an existing lobster pair lacks against bernstein's template. Read-only.

PLAN.md (Settled 55) is the specification. Exit codes: 0 nothing missing, 1 something missing,
2 bad arguments or settings, 4 the template cannot be read.
"""

import argparse
import datetime
import json
import os
import re
import shlex

from bernstein.conduct import (
    ProjectRefused,
    locate,
    non_code_folder_in,
    read_conf_file,
    tools_folders,
    tools_folders_in,
)
from bernstein.newlobster import OUTER_FILES, OUTER_FOLDERS
from bernstein.render import INCLUDE, PLACEHOLDER, TemplateRefused, fill, values_for
from bernstein.settings import SettingsRefused, read_settings

# A template heading with one of these names the pair, so every pair's CLAUDE.md must have it.
PAIR_NAMES = {"NAME", "TOOLS", "SELF", "SISTER"}
# The shared sections whose wording the template fixes; the others carry a date or a project's own lines.
FIXED_WORDING = {"sections/inbox.md", "sections/mail.md"}


def hook_has_root(text, root):
    """Whether a hook's JSON text passes this mail root to --root, as one shell word."""
    word = json.dumps(shlex.quote(root), ensure_ascii=False)[1:-1]
    return re.search(rf' --root {re.escape(word)}(?=[\s"])', text) is not None


def sections_of(text):
    """Each "## " section as {heading: its lines}, leaving out blank lines and a closing ---."""
    found, lines = {}, []
    for line in text.splitlines():
        if line.startswith("## "):
            lines = found.setdefault(line, [])
        elif line.strip():
            lines.append(line)
    for lines in found.values():
        while lines and lines[-1] == "---":
            lines.pop()
    return found


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
        if (settings.get(key) or "") != value:
            said = f" (it says {settings[key]})" if settings.get(key) else ""
            shown = f"{key}={value}" if value else f"{key}= (empty: a lone claw)"
            gaps.append(f"{shown} in lobster.conf{said}")
    gaps += [f"{key} in lobster.conf" for key in ("MODEL", "EFFORT") if not settings.get(key)]
    return gaps


def claws_of(conf):
    """The further claws a non-code project's lobster.conf names, or none."""
    try:
        return read_conf_file(conf).get("CLAWS", "").split()
    except (UnicodeDecodeError, OSError):
        return []


def required_sections(s, kind, non_code, tools, public, home, claws=()):
    """(headings, wording) for a half's CLAUDE.md. Headings: every heading of each section the template's
    CLAUDE.md for that half includes from common/sections/, and every heading of its own that names the
    pair. Wording: {heading: lines} of the included sections in FIXED_WORDING, filled. A lone claw has
    non_code None."""
    values = values_for(non_code, kind, model=s["MODEL"], effort=s["EFFORT"], non_code_dir=s["NON_CODE_DIR"],
                        code_dir=s["CODE_DIR"], mail_root=s["MAIL_ROOT"], lobster_mail=s["LOBSTER_MAIL"],
                        public=public, today=datetime.date.today(), home=home, tools=tools, claws=claws)
    where = f"{kind}/CLAUDE.md"
    with open(os.path.join(s["TEMPLATE"], kind, "CLAUDE.md"), encoding="utf-8") as f:
        raw = f.read()
    headings, wording = [], {}
    for line in raw.splitlines():
        include = INCLUDE.fullmatch(line)
        if include:
            name = fill(include.group(1), values, where)
            section = os.path.join(s["TEMPLATE"], "common", name)
            with open(section, encoding="utf-8") as f:
                text = f.read()
            headings += [fill(h, values, section) for h in text.splitlines() if h.startswith("## ")]
            if name in FIXED_WORDING:
                wording.update(sections_of(fill(text, values, section)))
        elif line.startswith("## ") and set(PLACEHOLDER.findall(line)) & PAIR_NAMES:
            headings.append(fill(line, values, where))
    return headings, wording


def claude_gaps(folder, headings, wording):
    claude = os.path.join(folder, "CLAUDE.md")
    if not os.path.isfile(claude):
        return ["CLAUDE.md"]
    with open(claude, encoding="utf-8", errors="replace") as f:
        text = f.read()
    have = sections_of(text)
    return ([f'the section "{h}" in CLAUDE.md' for h in headings if h not in have]
            + [f'the template\'s wording of the section "{h}" in CLAUDE.md'
               for h, lines in wording.items() if h in have and have[h] != lines])


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
        elif not hook_has_root(text, s["MAIL_ROOT"]):
            gaps.append(f"--root {shlex.quote(s['MAIL_ROOT'])} in the lobster-mail start hook in .claude/settings.json")
    if not os.path.isfile(os.path.join(folder, "inbox", "README.md")):
        gaps.append("inbox/README.md")
    non_code, tools = (name, sister) if kind == "non-code" else (sister or None, name)
    claws = claws_of(conf) if kind == "non-code" else []
    for claw in claws:
        if not os.path.isdir(tools_folders(claw, s["CODE_DIR"])[1]):
            gaps.append(f"the claw {claw} in {s['CODE_DIR']} or a folder directly inside it")
    gaps += claude_gaps(folder, *required_sections(s, kind, non_code, tools, found[0] != found[1], s["HOME"], claws))
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
    p = Parser(prog="conform", description="List what an existing lobster pair, or a lone claw (a tools project "
               "with no non-code half), lacks against bernstein's lobster-project template. Reads only; changes nothing.")
    p.add_argument("project", help="the non-code project's name; or, alone, a lone claw's")
    p.add_argument("tools", nargs="?", help="the non-code project's home tools project")
    return p


def lone_or(non_code, tools, s):
    """The sister a home claw's lobster.conf should name: the non-code project, unless the claw says it is a
    lone claw (an empty SISTER), which serves this project among others and is checked as one."""
    try:
        found = find(tools, "code", s)
    except ProjectRefused:
        return non_code
    if found is None:
        return non_code
    conf = os.path.join(found[0], "lobster.conf")
    if not os.path.isfile(conf):
        return non_code
    try:
        settings = read_conf_file(conf)
    except (UnicodeDecodeError, OSError):
        return non_code
    return "" if "SISTER" in settings and not settings["SISTER"] else non_code


def report(a, s, out):
    """Write the report; return the number of things missing."""
    total = 0
    halves = ((a.project, "non-code", a.tools), (a.tools, "code", lone_or(a.project, a.tools, s))) if a.tools else (
        (a.project, "code", ""),)
    for name, kind, sister in halves:
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
        a = parser().parse_args(argv)
        total = report(a, s, out)
    except Stop as stopped:
        err.write(f"conform: {stopped.message}\n")
        return stopped.code
    if total:
        out.write(f"{total} thing{'s' if total != 1 else ''} to bring into line.\n")
        return 1
    out.write("Both halves are in line.\n" if a.tools else "The claw is in line.\n")
    return 0
