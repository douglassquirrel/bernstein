"""Rendering bernstein's lobster-project template for one half of a new pair."""

import json
import os
import re
import shlex


class TemplateRefused(ValueError):
    """The template cannot be used; the message says where and why."""


MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December")
PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")
INCLUDE = re.compile(r"^\{\{> (sections/[^\n]+)\}\}$", re.MULTILINE)


def fill(text, values, where):
    """Fill every all-capitals placeholder; leave any other {{...}} exactly as written."""
    def one(match):
        name = match.group(1)
        if name not in values:
            raise TemplateRefused(f"{where}: unknown placeholder {{{{{name}}}}}")
        return values[name]
    return PLACEHOLDER.sub(one, text)


def resolve_includes(text, template_dir, values, where):
    """Replace each include line by its section from common/, filled."""
    def one(match):
        name = fill(match.group(1), values, where)
        path = os.path.join(template_dir, "common", name)
        if not os.path.isfile(path):
            raise TemplateRefused(f"{where}: the include {name} is not in common/")
        with open(path, encoding="utf-8") as f:
            return f.read().rstrip("\n")
    return INCLUDE.sub(one, text)


def files_under(folder):
    """Every file under folder, as paths relative to it, in a fixed order."""
    found = []
    for root, dirs, names in os.walk(folder):
        dirs.sort()
        for n in sorted(names):
            found.append(os.path.relpath(os.path.join(root, n), folder))
    return found


def render_half(template_dir, half, values, public):
    """Every file of one half, as {relative path: text}, includes resolved and placeholders filled."""
    own = os.path.join(template_dir, half)
    if not os.path.isdir(own):
        raise TemplateRefused(f"the template folder {template_dir} has no {half}/ folder")
    sources = [(rel, os.path.join(own, rel), half + "/" + rel) for rel in files_under(own)]
    for rel in ("inbox/README.md", "lobster.conf"):
        sources.append((rel, os.path.join(template_dir, "common", rel), "common/" + rel))
    rendered = {}
    for rel, path, where in sources:
        if half == "code" and rel == "LICENSE" and not public:
            continue
        if half == "code" and rel == "tools.conf.example":
            rel = values["TOOLS"] + ".conf.example"
        if not os.path.isfile(path):
            raise TemplateRefused(f"the template has no {where}")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        rendered[rel] = fill(resolve_includes(text, template_dir, values, where), values, where)
        if rel.endswith(".json"):
            try:
                json.loads(rendered[rel])
            except ValueError:
                raise TemplateRefused(f"{where}: not valid JSON once filled in")
    return rendered


def tilde(path, home):
    """A path under home, written with ~."""
    if path == home or path.startswith(home + "/"):
        return "~" + path[len(home):]
    return path


def listed(names, mark=True):
    """Names as prose: `a`, `b` and `c` (or plain, without the backticks)."""
    shown = [f"`{n}`" if mark else n for n in names]
    if len(shown) <= 1:
        return "".join(shown)
    return ", ".join(shown[:-1]) + " and " + shown[-1]


def values_for(name, half, model, effort, non_code_dir, code_dir, mail_root, lobster_mail, public, today, home,
               tools=None, non_code_path=None, tools_path=None, claws=()):
    """The placeholder values for one half of the pair named `name`; an existing pair may give its own
    tools name and folders. `claws` are the further claws a non-code project uses besides its home,
    `tools`. A lone claw (a tools project with no sister) has `name` None and gives `tools`."""
    lone = name is None
    name = name or ""
    tools = tools or name + "-tools"
    if tools_path is None:
        tools_path = os.path.join(code_dir, tools + "-code", tools) if public else os.path.join(code_dir, tools)
    non_code_path = "" if lone else (non_code_path or os.path.join(non_code_dir, name))
    non_code = half == "non-code"
    nc_shown = tilde(non_code_path, home) if non_code_path else ""
    claws = list(claws)
    every = [tools] + claws
    mounts = [(f"| `~/mnt/{tools}` | the home claw, `{tools}`: **read and run only**; never write, commit, install or "
               "make a `.venv` in it |")]
    mounts += [f"| `~/mnt/{c}` | the claw `{c}`: read and run only, as above |" for c in claws]
    rows = [(f"| `{tools}` | {{{{to fill: as they are made}}}} | From `~/mnt/{tools}`, as its README says; the home "
             "claw, where new tools are born |")]
    rows += [f"| `{c}` | {{{{to fill: as they are used}}}} | From `~/mnt/{c}`, as its README says |" for c in claws]
    if lone:
        sister_words = {
            "SERVED": "any",
            "FOR_WHOM": "the work done in Squirrel's lobster projects (the ganglia), any of which may ask this claw "
                        "for a tool",
            "REQUESTER": "a lobster project",
            "SERVING": "Squirrel's lobster projects",
            "TALKS_TO": "the lobster projects it serves",
            "ASKING": "another project",
            "SEND_TO": "<project>",
            "OF_WHOM": f"`{tools}`, a claw: a tools project with no sister project, used by any lobster project that asks",
            "SISTER_FIRST_SESSION": "This claw has no sister project: ask Squirrel which lobster projects will use it "
                                    "first, and\n   read their CLAUDE.md (read only) for what their work is before "
                                    "offering answers for \"What this is\".",
        }
    else:
        sister_words = {
            "SERVED": "sister",
            "FOR_WHOM": f"the work done in the sister project, `{name}` (`{nc_shown}`)",
            "REQUESTER": f"`{name}`",
            "SERVING": f"`{name}`",
            "TALKS_TO": f"its sister project, `{name}`",
            "ASKING": f"`{name}`",
            "SEND_TO": name,
            "OF_WHOM": f"the lobster pair `{name}` and `{tools}`",
            "SISTER_FIRST_SESSION": "In this tools half, read the sister project's CLAUDE.md first (read only:\n"
                                    f"   {nc_shown}/CLAUDE.md, its Purpose and The brief) and offer its answers for "
                                    "\"What this is\",\n   so Squirrel need not say them twice.",
        }
    values = {
        "NAME": name,
        "TOOLS": tools,
        "SELF": name if non_code else tools,
        "SISTER": tools if non_code else name,
        "KIND": half,
        "PACKAGE": tools.replace("-", ""),
        "DATE": f"{today.day} {MONTHS[today.month - 1]} {today.year}",
        "YEAR": str(today.year),
        "MODEL": model[:1].upper() + model[1:],
        "MODEL_SETTING": model,
        "EFFORT": effort,
        "NONCODE_PATH": nc_shown,
        "TOOLS_PATH": tilde(tools_path, home),
        "MAIL_ROOT": tilde(mail_root, home),
        "MAIL_ROOT_SHELL": shlex.quote(mail_root),
        "LOBSTER_TOOLS": tilde(os.path.dirname(lobster_mail), home),
        "VISIBILITY": "public" if public else "private",
        "BACKLOG_PREFIX": (tools if lone else name).replace("-", "")[:2].upper(),
        "QUESTIONS_AT": 'CLAUDE.md, "Open questions for Squirrel"' if non_code else 'PLAN.md, "Open questions"',
        "CLAWS": " ".join(claws) if non_code else "",
        "CLAW_LIST": listed(every),
        "CLAW_NAMES": listed(every, mark=False),
        "OTHER_CLAWS": (f"It also uses the claws {listed(claws)}." if claws
                        else "It uses no other claw yet; when it comes to, `CLAWS` in `lobster.conf` names them."),
        "CLAW_MOUNTS": "\n".join(mounts),
        "CLAW_ROWS": "\n".join(rows),
    }
    values.update(sister_words)
    return values
