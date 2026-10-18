"""new-lobster: make a new lobster project, a non-code project and its tools project.

PLAN.md ("The command", "How it works") is the specification. Exit codes: 0 done (or a dry run),
2 bad arguments or settings, 3 something already in the way, 4 the template cannot be used,
5 a program it ran failed.
"""

import json
import os
import shlex
import subprocess

from bernstein.render import TemplateRefused, render_half, values_for
from bernstein.settings import (
    SettingsRefused,
    options_for_new_lobster,
    parser_for_new_lobster,
    read_settings,
)

# Files of a public tools project that stay in the outer folder, beside the checkout.
OUTER_FILES = ("CLAUDE.md", "PLAN.md", "DIARY.md", "START-HERE.txt", "lobster.conf")
OUTER_FOLDERS = ("inbox/", ".claude/")


class Stop(Exception):
    """Stop the run with an exit code and a message for standard error."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def read_conf(env):
    path = env.get("BERNSTEIN_CONF") or os.path.join(env["HOME"], ".bernstein.conf")
    if not os.path.exists(path):
        return path, ""
    with open(path, encoding="utf-8") as f:
        return path, f.read()


def run_program(argv, cwd, env, what, made):
    """Run one program; stop with exit 5 if it fails or cannot be run."""
    try:
        done = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    except OSError as why:
        raise Stop(5, f"{what} could not be run in {cwd} ({why.strerror}){already(made)}")
    if done.returncode != 0:
        detail = (done.stderr or done.stdout).strip()
        shown = "\n  " + detail if detail else ""
        raise Stop(5, f"{what} failed (exit {done.returncode}) in {cwd}{shown}{already(made)}")
    return done.stdout


def already(made):
    return "\nAlready made, and left as it is: {}".format(", ".join(made)) if made else ""


def in_the_way(o, env, folders):
    for folder in folders:
        if os.path.lexists(folder):
            raise Stop(3, f"{folder} already exists; nothing was made")
    listing = run_program([o.lobster_mail, "duty", "status", "--all", "--json", "--root", o.mail_root],
                          os.getcwd(), env, "lobster-mail duty status --all", [])
    try:
        found = json.loads(listing)
        names = {m["mailbox"] for m in found.get("mailboxes", [])} | set(found.get("skipped", []))
    except (ValueError, TypeError, KeyError, AttributeError):
        raise Stop(5, "lobster-mail duty status --all --json did not print the expected JSON")
    for box in (o.name, o.name + "-tools"):
        if box in names:
            raise Stop(3, f"the mailbox {box} already exists in {o.mail_root}; nothing was made")


def split_public(files):
    """For a public tools project: (outer folder's files, checkout's files)."""
    outer, checkout = {}, {}
    for rel, text in files.items():
        if rel in OUTER_FILES or rel.startswith(OUTER_FOLDERS):
            outer[rel] = text
        else:
            checkout[rel] = text
    return outer, checkout


def write_files(folder, files):
    for rel, text in sorted(files.items()):
        path = os.path.join(folder, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "x", encoding="utf-8") as f:
            f.write(text)


def quote(path):
    return shlex.quote(path)


def plan(o, nc, tools_outer, tools_repo):
    lines = [
        f"Make {o.name}: {nc}",
        "Make {}-tools: {}{}".format(o.name, tools_repo,
                                 f" (inside {tools_outer}, which holds its guidance files)"
                                 if tools_outer != tools_repo else ""),
        (f"Then: git init -b main in each repository; backlog init in each half; lobster-mail init {o.name} "
        f"and {o.name}-tools in {o.mail_root}; a first commit in each; the tools' .venv."),
    ]
    return lines


def report(o, nc, tools_outer, tools_repo, out):
    visibility = "public" if o.public else "private"
    out.write(f"Made {o.name}: {nc}\n")
    out.write(f"Made {o.name}-tools: {tools_outer}\n")
    out.write(f"Mailboxes {o.name} and {o.name}-tools in {o.mail_root}\n\n")
    out.write("GitHub is left to you. Create two repositories on github.com, empty:\n")
    out.write(f"  douglassquirrel/{o.name} (private)\n")
    out.write(f"  douglassquirrel/{o.name}-tools ({visibility})\n")
    out.write("then push each:\n")
    for folder, repo in ((nc, o.name), (tools_repo, o.name + "-tools")):
        out.write(f"  git -C {quote(folder)} remote add origin git@github.com:douglassquirrel/{repo}.git\n")
        out.write(f"  git -C {quote(folder)} push -u origin main\n")
    out.write("\nEach project's first session asks you for its purpose and brief.\n")


def render_into(o, env, today, out):
    """Render both halves into a new folder, for an existing pair; write nothing else."""
    tools = o.tools or o.name + "-tools"
    if os.path.lexists(o.render_into):
        raise Stop(3, f"{o.render_into} already exists; nothing was written")
    files = {}
    for half in ("non-code", "code"):
        values = values_for(o.name, half, model=o.model, effort=o.effort, non_code_dir=o.non_code_dir,
                            code_dir=o.code_dir, mail_root=o.mail_root, lobster_mail=o.lobster_mail,
                            public=o.public, today=today, home=env["HOME"], tools=tools,
                            non_code_path=o.non_code_path, tools_path=o.tools_path)
        try:
            rendered = render_half(o.template, half, values, o.public)
        except TemplateRefused as why:
            raise Stop(4, f"the template cannot be used: {why}")
        files.update({f"{half}/{rel}": text for rel, text in rendered.items()})
    if o.dry_run:
        out.write(f"Would render the template for {o.name} and {tools} into {o.render_into}: {len(files)} files\n")
        out.write("".join(f"  {rel}\n" for rel in sorted(files)))
        out.write("Dry run: nothing was written.\n")
        return
    os.makedirs(o.render_into)
    write_files(o.render_into, files)
    out.write(f"Rendered the template for {o.name} and {tools} into {o.render_into}: {len(files)} files. "
              "Nothing else was written.\n")


def make(o, env, today, out):
    if o.render_into:
        return render_into(o, env, today, out)
    home = env["HOME"]
    nc = os.path.join(o.non_code_dir, o.name)
    tools = o.name + "-tools"
    tools_outer = os.path.join(o.code_dir, tools + "-code") if o.public else os.path.join(o.code_dir, tools)
    tools_repo = os.path.join(tools_outer, tools) if o.public else tools_outer

    in_the_way(o, env, (nc, tools_outer))

    rendered = {}
    for half in ("non-code", "code"):
        values = values_for(o.name, half, model=o.model, effort=o.effort, non_code_dir=o.non_code_dir,
                            code_dir=o.code_dir, mail_root=o.mail_root, lobster_mail=o.lobster_mail,
                            public=o.public, today=today, home=home)
        try:
            rendered[half] = render_half(o.template, half, values, o.public)
        except TemplateRefused as why:
            raise Stop(4, f"the template cannot be used: {why}")
    package = tools.replace("-", "")
    rendered["code"][package + "/__init__.py"] = ""

    if o.dry_run:
        for line in plan(o, nc, tools_outer, tools_repo):
            out.write(line + "\n")
        out.write("Dry run: nothing was made.\n")
        return

    if o.public:
        outer_files, repo_files = split_public(rendered["code"])
    else:
        outer_files, repo_files = {}, rendered["code"]

    made = []
    for folder in (nc, tools_outer):
        try:
            os.makedirs(folder)
        except FileExistsError:
            raise Stop(3, f"{folder} appeared while new-lobster was running; it was left alone{already(made)}")
        made.append(folder)
    write_files(nc, rendered["non-code"])
    if o.public:
        os.makedirs(tools_repo)
        write_files(tools_outer, outer_files)
    write_files(tools_repo, repo_files)
    for empty in (os.path.join(nc, "reference"), os.path.join(nc, "_to_delete"),
                  os.path.join(tools_repo, "tests", "tier1"), os.path.join(tools_repo, "tests", "tier2")):
        os.makedirs(empty, exist_ok=True)

    for repo in (nc, tools_repo):
        run_program(["git", "init", "-b", "main"], repo, env, "git init", made)
        run_program(["git", "config", "user.name", "Claude"], repo, env, "git config", made)
        run_program(["git", "config", "user.email", "claude@douglassquirrel.com"], repo, env, "git config", made)
    prefix = o.name.replace("-", "")[:2]
    for folder, project in ((nc, o.name), (tools_outer, tools)):
        run_program(["backlog", "init", project, "--defaults", "--no-git", "--integration-mode", "none",
                     "--task-prefix", prefix, "--zero-padded-ids", "3"],
                    folder, env, f"backlog init {project}", made)
    for box in (o.name, tools):
        run_program([o.lobster_mail, "init", "--root", o.mail_root, box], os.getcwd(), env,
                    f"lobster-mail init {box}", made)
    commits = ((nc, rendered["non-code"], True, f"Start {o.name} from bernstein's lobster-project template"),
               (tools_repo, repo_files, not o.public, f"Start {tools} from the lobster-project template"))
    for repo, files, with_backlog, message in commits:
        run_program(["git", "add", "--"] + sorted(files) + (["backlog"] if with_backlog else []),
                    repo, env, "git add", made)
        run_program(["git", "commit", "-q", "-m", message], repo, env, "git commit", made)
    run_program([o.python, "-m", "venv", ".venv"], tools_repo, env, "making the tools' .venv", made)
    run_program([os.path.join(tools_repo, ".venv", "bin", "pip"), "install", "-q", "-r", "requirements-dev.txt"],
                tools_repo, env, "installing the tools' dev tooling", made)
    report(o, nc, tools_outer, tools_repo, out)


def main(argv, env, today, out, err):
    """Run new-lobster; return its exit code."""
    if "-h" in argv or "--help" in argv:
        out.write(parser_for_new_lobster().format_help())
        return 0
    try:
        path, text = read_conf(env)
        try:
            settings = read_settings(text, env["HOME"])
        except SettingsRefused as why:
            raise Stop(2, f"{path}: {why}")
        try:
            o = options_for_new_lobster(argv, settings)
        except SettingsRefused as why:
            raise Stop(2, f"{why} (new-lobster --help shows the form)")
        make(o, env, today, out)
    except Stop as stop:
        err.write(f"new-lobster: {stop.message}\n")
        return stop.code
    return 0
