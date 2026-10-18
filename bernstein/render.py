"""Rendering bernstein's lobster-project template for one half of a new pair."""

import os
import re


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
    return rendered


def tilde(path, home):
    """A path under home, written with ~."""
    if path == home or path.startswith(home + "/"):
        return "~" + path[len(home):]
    return path


def values_for(name, half, model, effort, non_code_dir, code_dir, mail_root, lobster_mail, public, today, home):
    """The placeholder values for one half of the pair named `name`."""
    tools = name + "-tools"
    tools_path = os.path.join(code_dir, tools + "-code", tools) if public else os.path.join(code_dir, tools)
    non_code = half == "non-code"
    return {
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
        "NONCODE_PATH": tilde(os.path.join(non_code_dir, name), home),
        "TOOLS_PATH": tilde(tools_path, home),
        "MAIL_ROOT": tilde(mail_root, home),
        "LOBSTER_TOOLS": tilde(os.path.dirname(lobster_mail), home),
        "VISIBILITY": "public" if public else "private",
        "BACKLOG_PREFIX": name.replace("-", "")[:2].upper(),
        "QUESTIONS_AT": 'CLAUDE.md, "Open questions for Squirrel"' if non_code else 'PLAN.md, "Open questions"',
    }
