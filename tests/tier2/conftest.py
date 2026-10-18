"""Stubs on PATH for new-lobster's external programs, and a run() that drives main().

Each stub records its arguments and working folder as one JSON line in calls.jsonl. A stub
fails when its name is listed in the file `fail` in the stub folder. The lobster-mail stub's
`duty status --all --json` prints the JSON in `duty.json` (default: no mailboxes).
"""

import datetime
import io
import json
import os
import sys
import textwrap

import pytest

from bernstein import newlobster

STUB = textwrap.dedent('''\
    #!{python}
    import json, os, sys
    here = {bin!r}
    name = os.path.basename(sys.argv[0])
    with open(os.path.join(here, "calls.jsonl"), "a") as log:
        log.write(json.dumps({{"prog": name, "args": sys.argv[1:], "cwd": os.getcwd()}}) + "\\n")
    fail = os.path.join(here, "fail")
    if os.path.exists(fail) and name in open(fail).read().split():
        sys.stderr.write(name + ": stub failure\\n")
        sys.exit(1)
    args = sys.argv[1:]
    if name == "lobster-mail" and args[:3] == ["duty", "status", "--all"]:
        duty = os.path.join(here, "duty.json")
        print(open(duty).read() if os.path.exists(duty) else json.dumps({{"root": "", "mailboxes": [], "skipped": []}}))
    if name == "python3" and args[:2] == ["-m", "venv"]:
        os.makedirs(os.path.join(args[2], "bin"))
        pip = os.path.join(args[2], "bin", "pip")
        with open(pip, "w") as f:
            f.write(open(__file__).read())
        os.chmod(pip, 0o755)
    sys.exit(0)
''')

TEMPLATE = {
    "README.md": "The test template.\n",
    "common/sections/rule.md": "Rule for {{SELF}}, sister {{SISTER}}.\n",
    "common/sections/repo-private.md": "{{TOOLS}} is private.\n",
    "common/sections/repo-public.md": "{{TOOLS}} is public.\n",
    "common/inbox/README.md": "Inbox of {{SELF}}.\n",
    "common/lobster.conf": "KIND={{KIND}}\nMODEL={{MODEL_SETTING}}\nEFFORT={{EFFORT}}\n",
    "non-code/CLAUDE.md": "# {{NAME}}\n\n{{> sections/rule.md}}\n\n{{to fill: the purpose}}\n",
    "non-code/START-HERE.txt": "Start {{NAME}} on {{DATE}}.\n",
    "non-code/.gitignore": "inbox/*\n",
    "code/CLAUDE.md": "# {{TOOLS}}\n{{> sections/repo-{{VISIBILITY}}.md}}\n",
    "code/START-HERE.txt": "Start {{TOOLS}}.\n",
    "code/PLAN.md": "Plan for {{TOOLS}}.\n",
    "code/pyproject.toml": "addopts = \"--cov={{PACKAGE}}\"\n",
    "code/requirements-dev.txt": "pytest\n",
    "code/tools.conf.example": "# ~/.{{TOOLS}}.conf\n",
    "code/LICENSE": "MIT {{YEAR}}\n",
}


def write_tree(root, files):
    for rel, text in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)


def tree(root):
    """Every file under root, with its bytes."""
    found = {}
    for here, _, names in os.walk(root):
        for n in names:
            p = os.path.join(here, n)
            with open(p, "rb") as f:
                found[os.path.relpath(p, root)] = f.read()
    return found


class World:
    def __init__(self, base):
        self.home = os.path.join(base, "home sq")          # a space, on purpose
        self.bin = os.path.join(base, "bin")
        self.template = os.path.join(base, "tmpl")
        self.non_code = os.path.join(self.home, "projects", "non-code")
        self.code = os.path.join(self.home, "projects", "code")
        self.mail = os.path.join(self.home, "projects", "mail")
        for d in (self.home, self.bin, self.non_code, self.code, self.mail):
            os.makedirs(d, exist_ok=True)
        write_tree(self.template, TEMPLATE)
        for prog in ("git", "backlog", "lobster-mail", "python3"):
            p = os.path.join(self.bin, prog)
            with open(p, "w") as f:
                f.write(STUB.format(python=sys.executable, bin=self.bin))
            os.chmod(p, 0o755)
        self.conf = os.path.join(base, "bernstein.conf")
        self.write_conf("")

    def write_conf(self, extra):
        with open(self.conf, "w") as f:
            f.write("TEMPLATE=%s\nNON_CODE_DIR=%s\nCODE_DIR=%s\nMAIL_ROOT=%s\nLOBSTER_MAIL=%s\nPYTHON=%s\n%s"
                    % (self.template, self.non_code, self.code, self.mail,
                       os.path.join(self.bin, "lobster-mail"), os.path.join(self.bin, "python3"), extra))

    def fail(self, *progs):
        with open(os.path.join(self.bin, "fail"), "w") as f:
            f.write(" ".join(progs))

    def mailboxes(self, names, skipped=()):
        with open(os.path.join(self.bin, "duty.json"), "w") as f:
            json.dump({"root": self.mail, "mailboxes": [{"mailbox": n, "duty": None} for n in names],
                       "skipped": list(skipped)}, f)

    def calls(self):
        p = os.path.join(self.bin, "calls.jsonl")
        if not os.path.exists(p):
            return []
        with open(p) as f:
            return [json.loads(line) for line in f]

    def run(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        env = {"PATH": self.bin + os.pathsep + "/usr/bin:/bin", "HOME": self.home, "BERNSTEIN_CONF": self.conf}
        code = newlobster.main(list(argv), env=env, today=datetime.date(2026, 10, 18), out=out, err=err)
        return code, out.getvalue(), err.getvalue()


@pytest.fixture
def world(tmp_path):
    return World(str(tmp_path))
