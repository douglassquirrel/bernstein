import os

SECTIONS = {
    "common/sections/rule.md": "## Mail\n\nMail for {{SELF}}.\n",
    "common/sections/repo-private.md": "## Inbox\n\n{{TOOLS}} is private.\n",
    "common/sections/repo-public.md": "## Inbox\n\n{{TOOLS}} is public.\n",
    "non-code/CLAUDE.md": "# {{NAME}}\n\n## The pair: {{NAME}} and {{TOOLS}}\n\n{{> sections/rule.md}}\n\n## Own\n",
    "code/CLAUDE.md": "# {{TOOLS}}\n\n## The sister project: {{NAME}}\n\n{{> sections/repo-{{VISIBILITY}}.md}}\n",
}

HOOK = '{"command": "\\"$HOME/l/lobster-mail\\" start --project \\"$CLAUDE_PROJECT_DIR\\""}\n'


def lobster_template(world):
    """The test template, with headings in its sections and the pair named in a heading."""
    for rel, text in SECTIONS.items():
        with open(os.path.join(world.template, rel), "w") as f:
            f.write(text)


def write(folder, files):
    for rel, text in files.items():
        p = os.path.join(folder, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)


def half_in_line(folder, kind, self_, sister, claude):
    write(folder, {"lobster.conf": f"KIND={kind}\nSELF={self_}\nSISTER={sister}\nMODEL=opus\nEFFORT=high\n",
                   "START-HERE.txt": "Start.\n", ".claude/settings.json": HOOK, "inbox/README.md": "Inbox.\n",
                   "CLAUDE.md": claude})
    os.makedirs(os.path.join(folder, "backlog"))


def pair_in_line(world, public=False, under=""):
    """A pair that has everything the template gives it: (non-code folder, tools folder, tools checkout)."""
    lobster_template(world)
    nc = os.path.join(world.non_code, under, "recipes")
    half_in_line(nc, "non-code", "recipes", "recipes-tools",
                 "# recipes\n\n## The pair: recipes and recipes-tools\n\n## Mail\n\nOurs.\n")
    os.makedirs(os.path.join(nc, ".git"))
    outer = os.path.join(world.code, under, "recipes-tools-code" if public else "recipes-tools")
    half_in_line(outer, "code", "recipes-tools", "recipes",
                 "# recipes-tools\n\n## The sister project: recipes\n\n## Inbox\n\nOurs.\n")
    checkout = os.path.join(outer, "recipes-tools") if public else outer
    os.makedirs(os.path.join(checkout, ".git"))
    for box in ("recipes", "recipes-tools"):
        os.makedirs(os.path.join(world.mail, box))
    return nc, outer, checkout


def test_a_pair_with_everything_the_template_gives_is_in_line(world):
    nc, outer, _checkout = pair_in_line(world)
    code, out, err = world.conform("recipes", "recipes-tools")
    assert (code, err) == (0, "")
    assert out == (f"recipes (non-code): {nc}\n  in line\n"
                   f"recipes-tools (code): {outer}\n  in line\n"
                   "Both halves are in line.\n")


def test_missing_lobster_files_are_each_listed_and_the_exit_is_1(world):
    nc, outer, _checkout = pair_in_line(world)
    os.remove(os.path.join(nc, "lobster.conf"))
    os.remove(os.path.join(outer, "START-HERE.txt"))
    os.remove(os.path.join(outer, "inbox", "README.md"))
    with open(os.path.join(outer, ".claude", "settings.json"), "w") as f:
        f.write("{}\n")
    os.remove(os.path.join(nc, ".claude", "settings.json"))
    code, out, err = world.conform("recipes", "recipes-tools")
    assert (code, err) == (1, "")
    assert out == (f"recipes (non-code): {nc}\n"
                   "  missing: lobster.conf\n"
                   "  missing: .claude/settings.json (the lobster-mail start hook)\n"
                   f"recipes-tools (code): {outer}\n"
                   "  missing: START-HERE.txt\n"
                   "  missing: the lobster-mail start hook in .claude/settings.json\n"
                   "  missing: inbox/README.md\n"
                   "5 things to bring into line.\n")


def test_a_lobster_conf_with_wrong_or_missing_values_says_which(world):
    nc, outer, _checkout = pair_in_line(world)
    with open(os.path.join(nc, "lobster.conf"), "w") as f:
        f.write("KIND=code\nSELF=recipes\nSISTER=soups-tools\nEFFORT=high\n")
    with open(os.path.join(outer, "lobster.conf"), "wb") as f:
        f.write(b"KIND=code\xff\n")
    code, out, _err = world.conform("recipes", "recipes-tools")
    assert code == 1
    assert out == (f"recipes (non-code): {nc}\n"
                   "  missing: KIND=non-code in lobster.conf (it says code)\n"
                   "  missing: SISTER=recipes-tools in lobster.conf (it says soups-tools)\n"
                   "  missing: MODEL in lobster.conf\n"
                   f"recipes-tools (code): {outer}\n"
                   "  missing: lobster.conf as plain UTF-8 text\n"
                   "4 things to bring into line.\n")


def test_claude_md_needs_the_templates_shared_sections_and_the_heading_naming_the_pair(world):
    nc, outer, _checkout = pair_in_line(world)
    with open(os.path.join(nc, "CLAUDE.md"), "w") as f:
        f.write("# recipes\n\n## The pair: recipes and soups\n\n## Own\n")
    os.remove(os.path.join(outer, "CLAUDE.md"))
    code, out, _err = world.conform("recipes", "recipes-tools")
    assert code == 1
    assert out == (f"recipes (non-code): {nc}\n"
                   "  missing: the section \"## The pair: recipes and recipes-tools\" in CLAUDE.md\n"
                   "  missing: the section \"## Mail\" in CLAUDE.md\n"
                   f"recipes-tools (code): {outer}\n"
                   "  missing: CLAUDE.md\n"
                   "3 things to bring into line.\n")


def test_each_half_needs_a_git_repository_backlog_and_a_mailbox(world):
    nc, outer, _checkout = pair_in_line(world, public=True, under="kitchen")
    os.rmdir(os.path.join(nc, ".git"))
    os.rmdir(os.path.join(outer, "backlog"))
    os.rmdir(os.path.join(world.mail, "recipes-tools"))
    code, out, _err = world.conform("recipes", "recipes-tools")
    assert code == 1
    assert out == (f"recipes (non-code): {nc}\n"
                   f"  missing: a git repository in {nc}\n"
                   f"recipes-tools (code): {outer}\n"
                   f"  missing: backlog/ in {outer}\n"
                   f"  missing: the mailbox recipes-tools in {world.mail}\n"
                   "3 things to bring into line.\n")


def test_a_public_checkout_must_not_hold_the_files_that_belong_beside_it(world):
    nc, outer, checkout = pair_in_line(world, public=True)
    write(checkout, {"CLAUDE.md": "old\n", "DIARY.md": "old\n", "inbox/README.md": "old\n", "README.md": "fine\n"})
    code, out, _err = world.conform("recipes", "recipes-tools")
    assert code == 1
    assert out == (f"recipes (non-code): {nc}\n  in line\n"
                   f"recipes-tools (code): {outer}\n"
                   f"  missing: CLAUDE.md beside the checkout, not in it ({checkout})\n"
                   f"  missing: DIARY.md beside the checkout, not in it ({checkout})\n"
                   f"  missing: inbox/ beside the checkout, not in it ({checkout})\n"
                   "3 things to bring into line.\n")


def test_a_half_that_cannot_be_found_or_is_in_two_places_is_reported_and_the_other_is_still_checked(world):
    nc, outer, _checkout = pair_in_line(world)
    code, out, _err = world.conform("soups", "recipes-tools")
    assert code == 1
    assert out == ("soups (non-code): not found\n"
                   f"  soups is not in {world.non_code} or a folder directly inside it\n"
                   f"recipes-tools (code): {outer}\n"
                   "  missing: SISTER=soups in lobster.conf (it says recipes)\n"
                   "  missing: the section \"## The sister project: soups\" in CLAUDE.md\n"
                   "3 things to bring into line.\n")
    a, b = os.path.join(world.code, "a", "recipes-tools"), os.path.join(world.code, "b", "recipes-tools")
    os.makedirs(a)
    os.makedirs(b)
    os.rename(outer, os.path.join(world.code, "gone"))
    code, out, _err = world.conform("recipes", "recipes-tools")
    assert code == 1
    assert out == (f"recipes (non-code): {nc}\n  in line\n"
                   "recipes-tools (code): not found\n"
                   f"  recipes-tools is in two places, {a} and {b}: keep one, or rename the other\n"
                   "1 thing to bring into line.\n")


def test_help_bad_arguments_bad_settings_and_an_unreadable_template_are_plain_errors(world):
    code, out, _err = world.conform("--help")
    assert code == 0 and out.startswith("usage: conform [-h] non_code tools")
    code, _out, err = world.conform("recipes")
    assert code == 2 and err.startswith("conform: ") and err.endswith("(conform --help shows the form)\n")
    world.write_conf("EFFORT=extreme\n")
    code, _out, err = world.conform("recipes", "recipes-tools")
    assert (code, err) == (2, f"conform: {world.conf}: line 7: EFFORT must be one of low, medium, high, xhigh, max\n")
    world.write_conf("")
    pair_in_line(world)
    os.remove(os.path.join(world.template, "common", "sections", "rule.md"))
    code, _out, err = world.conform("recipes", "recipes-tools")
    assert code == 4 and err.startswith("conform: the template cannot be read: ")


def test_the_conform_command_file_runs_as_a_program(tmp_path):
    import subprocess
    import sys
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    done = subprocess.run([sys.executable, os.path.join(here, "conform"), "--help"],
                          capture_output=True, text=True, check=False,
                          env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("usage: conform")


def test_a_heading_with_a_date_or_other_value_is_not_required_only_one_naming_the_pair(world):
    pair_in_line(world)
    with open(os.path.join(world.template, "non-code", "CLAUDE.md"), "a") as f:
        f.write("\n## Where things stand (updated {{DATE}})\n\n## Run by {{MODEL}}\n")
    code, out, _err = world.conform("recipes", "recipes-tools")
    assert (code, out.splitlines()[-1]) == (0, "Both halves are in line.")
