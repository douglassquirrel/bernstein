"""conduct: start a lobster project's session, or ask a running one to hand over and stop.

PLAN.md ("The start and stop tool", "As built") is the specification. Exit codes: 0 done, 2 bad
arguments or settings, 3 no such project or mailbox (or, for start, a session already running),
4 a program failed or the duty listing could not be read, 5 --wait ran out.
"""

import argparse
import json
import os
import subprocess
import urllib.parse
from types import SimpleNamespace

from bernstein.render import MONTHS
from bernstein.settings import SettingsRefused, read_settings

PACES = ("eager", "normal", "relaxed")
WAIT_STEP = 10
CHANGING_TRIES = 3


class ProjectRefused(ValueError):
    """The project cannot be found; the message says why."""


class Stop(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def day(today):
    return f"{today.day} {MONTHS[today.month - 1]} {today.year}"


def start_message(brief, today):
    """The body of the Start message: follow START-HERE.txt, then the brief or wait."""
    text = (f"Start (from bernstein, {day(today)}).\n\n"
            "Squirrel has started this session through bernstein. Follow START-HERE.txt in this\n"
            "project's folder from the top: step 0 (the model and effort question) first, then the\n"
            "mail and the rest.\n\n")
    if brief is None:
        return text + "Then wait for Squirrel.\n"
    return text + "Then this brief, from Squirrel:\n\n" + brief


def stop_message(today):
    """The body of the Stop message: hand over at the next safe point."""
    return (f"Stop (from bernstein, {day(today)}).\n\n"
            "Squirrel has asked this session to hand over and stop. At the next safe point (nothing\n"
            "half-edited, nothing half-committed): bring the record up to date, send the handover with\n"
            "lobster-mail handover, stop watching mail and stop the check-in chain, tell Squirrel in\n"
            "chat that bernstein asked you to hand over, and do nothing more unless he says.\n")


def read_conf_file(path):
    found = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                found[key.strip()] = value.strip()
    return found


def subfolders(base):
    """The folders directly inside base, by name, leaving out hidden ones."""
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return []
    return [os.path.join(base, n) for n in names if not n.startswith(".") and os.path.isdir(os.path.join(base, n))]


def tools_folders_in(name, base):
    """(folder holding START-HERE.txt and lobster.conf, checkout) for a tools project in base, or None."""
    outer = os.path.join(base, name + "-code")
    if os.path.isdir(outer):
        return outer, os.path.join(outer, name)
    plain = os.path.join(base, name)
    return (plain, plain) if os.path.isdir(plain) else None


def non_code_folder_in(name, base):
    folder = os.path.join(base, name)
    return folder if os.path.isdir(folder) else None


def locate(name, base, found_in):
    """What found_in finds directly in base, else in the one subfolder holding it; None if none."""
    direct = found_in(name, base)
    if direct:
        return direct
    found = [f for f in (found_in(name, d) for d in subfolders(base)) if f]
    if len(found) > 1:
        places = [f[0] if isinstance(f, tuple) else f for f in found]
        count = {2: "two", 3: "three"}.get(len(places), str(len(places)))
        raise ProjectRefused(f"{name} is in {count} places, {', '.join(places[:-1])} and {places[-1]}: "
                             "keep one, or rename the other")
    return found[0] if found else None


def tools_folders(name, code_dir):
    """(folder, checkout) for a tools project in code_dir or one of its subfolders; where it would be if neither."""
    plain = os.path.join(code_dir, name)
    return locate(name, code_dir, tools_folders_in) or (plain, plain)


def find_project(name, non_code_dir, code_dir):
    """Where a lobster project is, and what lobster.conf says about it."""
    if name.endswith("-tools"):
        folder, checkout = tools_folders(name, code_dir)
    else:
        folder = checkout = locate(name, non_code_dir, non_code_folder_in) or os.path.join(non_code_dir, name)
    if not os.path.isdir(folder):
        base = code_dir if name.endswith("-tools") else non_code_dir
        raise ProjectRefused(f"no project {name} in {base} or a folder directly inside it")
    conf = os.path.join(folder, "lobster.conf")
    if not os.path.isfile(conf):
        raise ProjectRefused(f"{folder} has no lobster.conf: is it a lobster project?")
    try:
        settings = read_conf_file(conf)
    except UnicodeDecodeError:
        raise ProjectRefused(f"{conf} is not plain UTF-8 text: save it again as UTF-8")
    except OSError as why:
        raise ProjectRefused(f"{conf} cannot be read ({why.strerror}): check its permissions")
    kind = settings.get("KIND", "code" if name.endswith("-tools") else "non-code")
    if kind not in ("code", "non-code"):
        raise ProjectRefused(f"{conf} says KIND={kind}: it must be code or non-code")
    if not os.path.isfile(os.path.join(folder, "START-HERE.txt")):
        raise ProjectRefused(f"{folder} has no START-HERE.txt, which the session is told to follow: "
                             "bring the project into line with the lobster template first")
    for key, example in (("MODEL", "opus"), ("EFFORT", "high")):
        if not settings.get(key):
            raise ProjectRefused(f"{conf} has no {key}, which START-HERE.txt step 0 reads: "
                                 f"add a line such as {key}={example}")
    sister = settings.get("SISTER", "")
    if kind == "non-code" and not sister:
        raise ProjectRefused(f"{conf} has no SISTER, the tools project a non-code session works with: "
                             f"add a line such as SISTER={name}-tools")
    sister_checkout = tools_folders(sister, code_dir)[1] if kind == "non-code" else None
    if sister_checkout and not os.path.isdir(sister_checkout):
        raise ProjectRefused(f"the sister tools project {sister} is not in {code_dir} or a folder directly "
                             f"inside it: make it, or correct SISTER in {conf}")
    return SimpleNamespace(name=name, kind=kind, folder=folder, checkout=checkout, sister=sister,
                           sister_checkout=sister_checkout, model=settings.get("MODEL", ""),
                           effort=settings.get("EFFORT", ""))


def encode(params):
    return urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def link_for(project, mail_root, lobster_tools):
    """The documented desktop-app link that opens the project's session with its first line."""
    if project.kind == "non-code":
        folders = [project.folder, mail_root] + ([project.sister_checkout] if project.sister_checkout else [])
        folders.append(lobster_tools)
        q = (f"Read START-HERE.txt in the {project.name} folder (mounted at ~/mnt/{project.name}) and do "
             f"what it says, starting with its step 0 before anything else. If ~/mnt/{project.name} is not "
             f"there, say \"the app opened me without the {project.name} folder\" and stop.")
        return "claude://cowork/new?" + encode([("folder", f) for f in folders] + [("q", q)])
    q = (f"This session must work in {project.folder}. If your working folder is anything else, say \"the app "
         "opened me in the wrong folder\" and stop. Otherwise read START-HERE.txt there and do what it says, "
         "starting with its step 0 before anything else.")
    return "claude://code/new?" + encode([("folder", project.folder), ("q", q)])


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SettingsRefused(message)


def parser():
    p = Parser(prog="conduct", description="Start a lobster project's session, or ask a running one to "
               "hand over and stop, by mail as bernstein.",
               epilog="conduct start <project> [--brief FILE] [--pace LEVEL] [--dry-run]\n"
                      "conduct stop <project> | --all [--wait SECONDS] [--dry-run]",
               formatter_class=argparse.RawDescriptionHelpFormatter)
    verbs = p.add_subparsers(dest="verb", parser_class=Parser)
    s = verbs.add_parser("start", help="send a Start message and open the project's session")
    s.add_argument("project")
    s.add_argument("--brief", metavar="FILE", help="a file whose text is sent as the session's brief")
    s.add_argument("--pace", choices=PACES, help="set the mailbox's mail pace first")
    s.add_argument("--dry-run", action="store_true", help="show the message and the link; send and open nothing")
    t = verbs.add_parser("stop", help="ask a running session to hand over and stop")
    t.add_argument("project", nargs="?")
    t.add_argument("--all", action="store_true", help="every session on duty except bernstein's")
    t.add_argument("--wait", type=int, metavar="SECONDS", help="wait this long for the handover")
    t.add_argument("--dry-run", action="store_true", help="show the message; send nothing")
    return p


def run(argv, env, what, stdin=None):
    try:
        done = subprocess.run(argv, input=stdin, env=env, capture_output=True, text=True, check=False)
    except OSError as why:
        raise Stop(4, f"{what} could not be run ({why.strerror})")
    if done.returncode != 0:
        detail = (done.stderr or done.stdout).strip()
        raise Stop(4, f"{what} failed (exit {done.returncode})" + ("\n  " + detail if detail else ""))
    return done.stdout


def listing(s, env, sleep):
    """The duty listing by mailbox, looking again while a duty is caught changing."""
    for tries in range(CHANGING_TRIES + 1):
        text = run([s["LOBSTER_MAIL"], "duty", "status", "--all", "--json", "--root", s["MAIL_ROOT"]],
                   env, "lobster-mail duty status --all")
        try:
            boxes = {m["mailbox"]: m for m in json.loads(text)["mailboxes"]}
        except (ValueError, KeyError, TypeError):
            raise Stop(4, "lobster-mail duty status --all --json did not print the expected JSON")
        changing = [n for n, m in boxes.items() if m.get("duty_changing")]
        if not changing:
            return boxes
        if tries == CHANGING_TRIES:
            raise Stop(4, f"the duty of {', '.join(changing)} kept changing while it was read; run conduct again")
        sleep(1)
    raise AssertionError("unreachable")  # pragma: no cover


def fresh(entry):
    duty = entry.get("duty")
    return duty is not None and not duty.get("stale")


def send(s, env, to, subject, body):
    run([s["LOBSTER_MAIL"], "send", "--as", "bernstein", "--to", to, "--subject", subject, "--root",
         s["MAIL_ROOT"], "-"], env, f"lobster-mail send to {to}", stdin=body)


def start(a, s, env, today, out, sleep):
    brief = None
    if a.brief is not None:
        try:
            with open(a.brief, encoding="utf-8") as f:
                brief = f.read()
        except OSError:
            raise Stop(2, f"the brief {a.brief} cannot be read")
    try:
        project = find_project(a.project, s["NON_CODE_DIR"], s["CODE_DIR"])
    except ProjectRefused as why:
        raise Stop(3, str(why))
    boxes = listing(s, env, sleep)
    if a.project not in boxes:
        raise Stop(3, f"there is no mailbox {a.project} in {s['MAIL_ROOT']}")
    if fresh(boxes[a.project]):
        d = boxes[a.project]["duty"]
        raise Stop(3, f"a session is already running for {a.project}: {d['holder']} has been on duty since "
                      f"{d['since']}, last beat {d['last_beat']}")
    body = start_message(brief, today)
    link = link_for(project, s["MAIL_ROOT"], os.path.dirname(s["LOBSTER_MAIL"]))
    if a.dry_run:
        out.write(f"Would send to {a.project}, as bernstein, subject \"Start: {a.project}\":\n\n{body}\n")
        out.write(f"Would open:\n  {link}\n")
        out.write("Dry run: nothing was sent or opened.\n")
        return
    if a.pace:
        run([s["LOBSTER_MAIL"], "pace", "--as", a.project, a.pace, "--root", s["MAIL_ROOT"]], env,
            f"lobster-mail pace {a.pace}")
    send(s, env, a.project, f"Start: {a.project}", body)
    out.write(f"Sent the Start message to {a.project}.\n")
    run(["open", link], env, "open")
    if project.kind == "non-code":
        out.write(f"Opened a Claude session for {a.project}: confirm its folders, then send its first line.\n")
    else:
        out.write(f"Opened a Claude Code session for {a.project}: confirm its folder, then send its first line.\n")
        out.write(f"Ask a bernstein session in the desktop app to set its model and effort to "
                  f"{project.model}, {project.effort}.\n")


def stop(a, s, env, today, out, sleep):
    if a.all == (a.project is not None):
        raise Stop(2, "name one project, or give --all")
    boxes = listing(s, env, sleep)
    if a.all:
        targets = [n for n, m in boxes.items() if n != "bernstein" and fresh(m)]
        if not targets:
            out.write("Nobody is on duty anywhere but bernstein: nothing to stop.\n")
            return
    else:
        if a.project not in boxes:
            raise Stop(3, f"there is no mailbox {a.project} in {s['MAIL_ROOT']}")
        if not fresh(boxes[a.project]):
            out.write(f"Nobody is on duty for {a.project}: nothing to stop.\n")
            return
        targets = [a.project]
    body = stop_message(today)
    if a.dry_run:
        out.write(f"Would send to {', '.join(targets)}, as bernstein, subject \"Stop: hand over\":\n\n{body}\n")
        out.write("Dry run: nothing was sent.\n")
        return
    for name in targets:
        send(s, env, name, "Stop: hand over", body)
        out.write(f"Sent the Stop message to {name}.\n")
    if a.wait is None:
        return
    waited = 0
    while True:
        boxes = listing(s, env, sleep)
        left = [n for n in targets if boxes.get(n, {}).get("duty") is not None
                or not boxes.get(n, {}).get("handover_waiting")]
        if not left:
            for name in targets:
                out.write(f"{name} has handed over.\n")
            return
        if waited >= a.wait:
            raise Stop(5, f"after {a.wait} seconds, still on duty: {', '.join(left)}")
        sleep(WAIT_STEP)
        waited += WAIT_STEP


def main(argv, env, today, out, err, sleep):
    """Run conduct; return its exit code."""
    if argv[:1] in (["-h"], ["--help"]) or (len(argv) == 2 and argv[1] in ("-h", "--help")):
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
        try:
            a = parser().parse_args(argv)
        except SettingsRefused as why:
            raise Stop(2, f"{why} (conduct --help shows the form)")
        if a.verb is None:
            raise Stop(2, "say start or stop (conduct --help shows the form)")
        (start if a.verb == "start" else stop)(a, s, env, today, out, sleep)
    except Stop as stopped:
        err.write(f"conduct: {stopped.message}\n")
        return stopped.code
    return 0
