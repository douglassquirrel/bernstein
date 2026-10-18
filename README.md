# bernstein

Tools that set up and run "lobster" projects: pairs of projects worked on with Claude, where a
non-code project does the work and asks a companion tools project, by mail, for every routine task
as a tested command. `new-lobster` makes such a pair in one step: both folders from a template,
git, a Backlog issue tracker, a mailbox each, and the first commits. `conduct` starts a project's
session and asks a running one to hand over. They are for one person's Mac and their own
projects; the projects talk by `lobster-mail`, from the
[lobster-tools](https://github.com/douglassquirrel/lobster-tools) repository.

## Requirements

- macOS with `/usr/bin/python3` (3.9 or later) and `git`.
- Backlog, the `backlog.md` package (`backlog` on `PATH`; tested with 1.53.0).
- A checkout of `lobster-tools` for `lobster-mail`, and a mail root it can use.
- A lobster-project template: a folder with `common/`, `non-code/` and `code/`. It is not part of
  this repository; `new-lobster` reads it from the `TEMPLATE` setting. See "The template" below.

## Installation

```bash
git clone https://github.com/douglassquirrel/bernstein.git
cd bernstein
cp bernstein.conf.example ~/.bernstein.conf      # then edit what differs on your machine
./new-lobster --help
```

## Quick start

See what would be made, without making anything:

```
$ ./new-lobster --dry-run recipes
Make recipes: /Users/me/projects/non-code/recipes
Make recipes-tools: /Users/me/projects/code/recipes-tools
Then: git init -b main in each repository; backlog init in each half; lobster-mail init recipes and recipes-tools in /Users/me/projects/mail; a first commit in each; the tools' .venv.
Dry run: nothing was made.
```

Then make it:

```
$ ./new-lobster recipes
Made recipes: /Users/me/projects/non-code/recipes
Made recipes-tools: /Users/me/projects/code/recipes-tools
Mailboxes recipes and recipes-tools in /Users/me/projects/mail

GitHub is left to you. Create two repositories on github.com, empty:
  douglassquirrel/recipes (private)
  douglassquirrel/recipes-tools (private)
then push each:
  git -C /Users/me/projects/non-code/recipes remote add origin git@github.com:douglassquirrel/recipes.git
  git -C /Users/me/projects/non-code/recipes push -u origin main
  git -C /Users/me/projects/code/recipes-tools remote add origin git@github.com:douglassquirrel/recipes-tools.git
  git -C /Users/me/projects/code/recipes-tools push -u origin main

Each project's first session asks you for its purpose and brief.
```

(Real output from a run into scratch folders, with the paths shortened.)

## Usage

```
new-lobster [--dry-run] [--public] [--template DIR] [--non-code-dir DIR] [--code-dir DIR]
            [--model MODEL] [--effort EFFORT] <name>
```

- `<name>`: the non-code project's name: lower-case letters, digits and single hyphens, starting
  with a letter, 2 to 40 characters, not ending in `-tools`. The tools project is `<name>-tools`.
- `--dry-run`: check everything and render every file, print what would be made, and stop.
  Nothing is written; the only program run is the read-only mailbox listing.
- `--public`: the tools project is public. Its guidance files then stay in an outer folder,
  `<name>-tools-code/`, beside a checkout `<name>-tools/` that holds the code and an MIT licence.
- `--template`, `--non-code-dir`, `--code-dir`, `--model`, `--effort`: override the settings below.

What it makes, for `recipes`: `<non-code dir>/recipes/` and `<code dir>/recipes-tools/`, each a git
repository on `main` with a first commit and Backlog (ids `RE-001` on); the mailboxes `recipes` and
`recipes-tools`; and the tools project's `.venv` with its dev tooling. It never writes over
anything, never changes the template, never deletes, and never touches GitHub.

### Settings

`~/.bernstein.conf` (or the file named by `BERNSTEIN_CONF`): `KEY=value` lines, `#` comments,
optional quotes, `~` for your home folder. All optional; `bernstein.conf.example` lists them:

| Setting | Default | Flag |
|---|---|---|
| `TEMPLATE` | `~/projects/code/bernstein-code/templates/lobster` | `--template` |
| `NON_CODE_DIR` | `~/projects/non-code` | `--non-code-dir` |
| `CODE_DIR` | `~/projects/code` | `--code-dir` |
| `MODEL` | `opus` | `--model` |
| `EFFORT` | `high` (`low`, `medium`, `high`, `xhigh` or `max`) | `--effort` |
| `LOBSTER_MAIL` | `~/projects/code/lobster-tools-code/lobster-tools/lobster-mail` | |
| `MAIL_ROOT` | `~/projects/mail` | |
| `PYTHON` | `/usr/bin/python3` | |

### The template

A folder with `common/sections/` (text shared by both halves), `common/inbox/README.md`,
`common/lobster.conf`, and the two halves' own files in `non-code/` and `code/`. In any file, a line
that is exactly `{{> sections/<file>.md}}` is replaced by that file from `common/sections/` (the
name may contain `{{VISIBILITY}}`), and a placeholder whose name is only capital letters and
underscores, such as `{{NAME}}`, `{{TOOLS}}`, `{{SELF}}`, `{{SISTER}}`, `{{DATE}}`, `{{MODEL}}` or
`{{EFFORT}}`, is filled in; an unknown one is an error. Any other `{{…}}` is left as written, for
the project's first session to complete.

## conduct: starting and stopping a project's session

```
conduct start <project> [--brief FILE] [--pace eager|normal|relaxed] [--dry-run]
conduct stop  <project> | --all  [--wait SECONDS] [--dry-run]
```

`conduct` talks to a lobster project's session by mail, as `bernstein`; each project's guidance
says to act on bernstein's mail at once. It reads who is on duty with `lobster-mail duty status
--all`, and never writes in a project's folder.

- **`start`** refuses if a session is already on duty for the project. Otherwise it sets the mail
  pace if `--pace` is given, mails a Start message (follow `START-HERE.txt` from the top, then the
  brief from `--brief FILE`, or wait), and opens the session in the Claude desktop app with the
  documented link: a Claude session for a non-code project, with its folder, the mail root, its
  tools project and `lobster-tools` connected; a Claude Code session for a tools project. You
  confirm the folders and send the prefilled first line. For a Claude Code session it reminds you
  to have a bernstein session set its model and effort, which a program cannot do.
- **`stop`** mails a Stop message: hand over at the next safe point, then stop. `--all` asks every
  session on duty except bernstein's. `--wait SECONDS` waits for each handover, looking every 10
  seconds.
- **`--dry-run`** shows the message and the link, and sends and opens nothing.

`start` checks the project before it sends or opens anything, and refuses (exit 3) with a message
saying what to fix when any part a lobster project has is missing: the folder (`<CODE_DIR>/<name>`
or `<CODE_DIR>/<name>-code` for a tools project, `<NON_CODE_DIR>/<name>` otherwise), a
`lobster.conf` it can read as UTF-8 text, a KIND of `code` or `non-code`, `START-HERE.txt`, MODEL
and EFFORT lines, and, for a non-code project, a SISTER line naming a tools project that exists.
A project made before the lobster template needs these before `conduct` can start it.

A session sees mail at its own pace: at once when eager, at the next pause when normal, only at
the end of a turn when relaxed. So a Stop to a relaxed session waits until you next talk to it.

| Code | Meaning |
|---|---|
| 0 | Sent (and, with `--wait`, handed over); or, for `stop`, nobody on duty |
| 2 | Bad arguments or settings |
| 3 | No such project or mailbox, or the project lacks a part `start` needs; or, for `start`, a session is already on duty |
| 4 | A program failed, or the duty listing could not be read |
| 5 | `--wait` ran out before the handover arrived |

## Errors and exit codes

Every failure is one line on standard error starting `new-lobster:`, saying what happened.

| Code | Meaning | What to do |
|---|---|---|
| 0 | Done, or a dry run | |
| 2 | A bad name, flag or settings line | The message names the rule or the line; `--help` shows the form |
| 3 | A folder or a mailbox it would make already exists | Choose another name, or move the existing one yourself |
| 4 | The template cannot be used (missing, a missing include, an unknown placeholder) | Fix the template; nothing was written |
| 5 | A program it runs failed (`git`, `backlog`, `lobster-mail`, Python) | The message says what failed and lists what was already made, which is left as it is |

## Testing

```bash
/usr/bin/python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest            # all tests, with coverage
.venv/bin/ruff check .      # lint
```

`tests/tier1/` tests the pure parts (names, settings, rendering) against small invented templates;
`tests/tier2/` runs `new-lobster` end to end against stubs of `git`, `backlog`, `lobster-mail` and
Python placed on `PATH`, and `conduct` against stubs of `lobster-mail` and `open`, with no network. Coverage is 99%: the two uncovered lines handle a folder
that appears while `new-lobster` is running, a race the tests cannot stage.

Manual check against the real programs (Tier 3): point `BERNSTEIN_CONF` at a settings file whose
`NON_CODE_DIR`, `CODE_DIR` and `MAIL_ROOT` are scratch folders, then run `./new-lobster --dry-run
<name>` and `./new-lobster <name>`, and look at what was made.

## Known limitations and non-goals

- The GitHub owner in the printed commands is fixed (`douglassquirrel`); creating repositories is
  left to the user.
- One pair at a time; no bulk or scheduled use; macOS only.
- The template is not shipped with this repository.

## Notes for users

- 18 October 2026: first versions of `new-lobster` and `conduct`.
- 18 October 2026: `conduct start` now refuses, sending and opening nothing, a project that lacks
  `START-HERE.txt`, a readable `lobster.conf`, a known KIND, MODEL or EFFORT, or (non-code) its
  sister tools project, instead of starting it or failing with a traceback.

## Contributing

Dev tooling (pytest, pytest-cov, ruff) goes in a `.venv` from `requirements-dev.txt`. Changes are
made test-first, on `main`.
