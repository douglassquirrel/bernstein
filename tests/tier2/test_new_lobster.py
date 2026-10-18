import os

from conftest import tree


def test_help_describes_the_command_and_exits_0(world):
    code, out, err = world.run("--help")
    assert code == 0
    assert "usage: new-lobster" in out and "--dry-run" in out and "--public" in out
    assert world.calls() == []


def test_a_bad_name_is_refused_with_exit_2_and_nothing_is_touched(world):
    code, out, err = world.run("Recipes")
    assert code == 2
    assert err == ("new-lobster: the name Recipes cannot be used: use only lower-case letters, "
                   "digits and hyphens (new-lobster --help shows the form)\n")
    assert world.calls() == [] and os.listdir(world.non_code) == [] and os.listdir(world.code) == []


def test_a_bad_settings_line_is_refused_with_exit_2_naming_the_file(world):
    world.write_conf("EFFORT=extreme\n")
    code, out, err = world.run("recipes")
    assert code == 2
    assert err == "new-lobster: %s: line 7: EFFORT must be one of low, medium, high, xhigh, max\n" % world.conf


def test_an_existing_folder_is_refused_with_exit_3_and_left_exactly_as_it_was(world):
    existing = os.path.join(world.code, "recipes-tools")
    os.makedirs(existing)
    with open(os.path.join(existing, "keep.txt"), "w") as f:
        f.write("mine\n")
    before = tree(world.code), tree(world.template)
    code, out, err = world.run("recipes")
    assert code == 3
    assert err == "new-lobster: %s already exists; nothing was made\n" % existing
    assert (tree(world.code), tree(world.template)) == before
    assert not os.path.exists(os.path.join(world.non_code, "recipes"))
    assert world.calls() == []


def test_an_existing_mailbox_is_refused_with_exit_3(world):
    world.mailboxes(["recipes"])
    code, out, err = world.run("recipes")
    assert code == 3
    assert err == "new-lobster: the mailbox recipes already exists in %s; nothing was made\n" % world.mail
    assert os.listdir(world.non_code) == []


def test_a_folder_of_that_name_in_the_mail_root_counts_as_in_the_way(world):
    world.mailboxes([], skipped=["recipes-tools"])
    code, out, err = world.run("recipes")
    assert code == 3
    assert "the mailbox recipes-tools already exists" in err


def test_a_template_with_an_unknown_placeholder_is_refused_with_exit_4_before_anything_is_written(world):
    with open(os.path.join(world.template, "code", "PLAN.md"), "w") as f:
        f.write("{{WHO}}\n")
    code, out, err = world.run("recipes")
    assert code == 4
    assert err == "new-lobster: the template cannot be used: code/PLAN.md: unknown placeholder {{WHO}}\n"
    assert os.listdir(world.non_code) == [] and os.listdir(world.code) == []


def test_a_missing_template_is_refused_with_exit_4(world):
    code, out, err = world.run("--template", os.path.join(world.home, "nowhere"), "recipes")
    assert code == 4
    assert "has no non-code/ folder" in err


def test_dry_run_writes_nothing_and_runs_only_the_duty_listing(world):
    code, out, err = world.run("--dry-run", "recipes")
    assert code == 0, err
    assert os.listdir(world.non_code) == [] and os.listdir(world.code) == []
    assert [c["prog"] for c in world.calls()] == ["lobster-mail"]
    assert "Dry run: nothing was made." in out
    assert os.path.join(world.non_code, "recipes") in out
    assert "git init -b main" in out and "lobster-mail init" in out


def made(world, name="recipes"):
    return os.path.join(world.non_code, name), os.path.join(world.code, name + "-tools")


def test_a_private_pair_is_made_with_both_folders_filled_in(world):
    code, out, err = world.run("recipes")
    assert code == 0, err
    nc, tools = made(world)
    nc_files, tools_files = tree(nc), tree(tools)
    assert nc_files["CLAUDE.md"] == b"# recipes\n\nRule for recipes, sister recipes-tools.\n\n{{to fill: the purpose}}\n"
    assert nc_files["START-HERE.txt"] == b"Start recipes on 18 October 2026.\n"
    assert nc_files["lobster.conf"] == b"KIND=non-code\nMODEL=opus\nEFFORT=high\n"
    assert nc_files["inbox/README.md"] == b"Inbox of recipes.\n"
    assert tools_files["CLAUDE.md"] == b"# recipes-tools\nrecipes-tools is private.\n"
    assert tools_files["recipes-tools.conf.example"] == b"# ~/.recipes-tools.conf\n"
    assert tools_files["recipestools/__init__.py"] == b""
    assert "LICENSE" not in tools_files
    for empty in (os.path.join(nc, "reference"), os.path.join(nc, "_to_delete"),
                  os.path.join(tools, "tests", "tier1"), os.path.join(tools, "tests", "tier2")):
        assert os.path.isdir(empty)


def test_the_programs_run_in_order_in_the_right_folders(world):
    code, out, err = world.run("recipes")
    assert code == 0, err
    nc, tools = made(world)
    lm = os.path.join(world.bin, "lobster-mail")
    got = [(c["prog"], c["args"], c["cwd"]) for c in world.calls()]
    nc_add = sorted(["CLAUDE.md", "START-HERE.txt", ".gitignore", "inbox/README.md", "lobster.conf"])
    tools_add = sorted(["CLAUDE.md", "START-HERE.txt", "PLAN.md", "pyproject.toml", "requirements-dev.txt",
                        "recipes-tools.conf.example", "inbox/README.md", "lobster.conf", "recipestools/__init__.py"])
    assert got == [
        ("lobster-mail", ["duty", "status", "--all", "--json", "--root", world.mail], os.getcwd()),
        ("git", ["init", "-b", "main"], nc),
        ("git", ["config", "user.name", "Claude"], nc),
        ("git", ["config", "user.email", "claude@douglassquirrel.com"], nc),
        ("git", ["init", "-b", "main"], tools),
        ("git", ["config", "user.name", "Claude"], tools),
        ("git", ["config", "user.email", "claude@douglassquirrel.com"], tools),
        ("backlog", ["init", "recipes", "--defaults", "--no-git", "--integration-mode", "none",
                     "--agent-instructions", "none", "--task-prefix", "re", "--zero-padded-ids", "3"], nc),
        ("backlog", ["init", "recipes-tools", "--defaults", "--no-git", "--integration-mode", "none",
                     "--agent-instructions", "none", "--task-prefix", "re", "--zero-padded-ids", "3"], tools),
        ("lobster-mail", ["init", "--root", world.mail, "recipes"], os.getcwd()),
        ("lobster-mail", ["init", "--root", world.mail, "recipes-tools"], os.getcwd()),
        ("git", ["add", "--"] + nc_add + ["backlog"], nc),
        ("git", ["commit", "-q", "-m", "Start recipes from bernstein's lobster-project template"], nc),
        ("git", ["add", "--"] + tools_add + ["backlog"], tools),
        ("git", ["commit", "-q", "-m", "Start recipes-tools from the lobster-project template"], tools),
        ("python3", ["-m", "venv", ".venv"], tools),
        ("pip", ["install", "-q", "-r", "requirements-dev.txt"], tools),
    ]
    assert lm == os.path.join(world.bin, "lobster-mail")


def test_the_report_names_both_folders_and_gives_the_github_steps(world):
    code, out, err = world.run("recipes")
    nc, tools = made(world)
    assert "Made recipes: %s" % nc in out
    assert "Made recipes-tools: %s" % tools in out
    assert "Mailboxes recipes and recipes-tools in %s" % world.mail in out
    assert "git@github.com:douglassquirrel/recipes.git" in out
    assert "git@github.com:douglassquirrel/recipes-tools.git" in out
    assert "git -C '%s' push -u origin main" % nc in out
    assert "(private)" in out


def test_a_public_tools_project_gets_the_outer_folder_with_the_checkout_inside(world):
    code, out, err = world.run("--public", "recipes")
    assert code == 0, err
    outer = os.path.join(world.code, "recipes-tools-code")
    checkout = os.path.join(outer, "recipes-tools")
    outer_files, checkout_files = tree(outer), tree(checkout)
    assert {"CLAUDE.md", "START-HERE.txt", "PLAN.md", "inbox/README.md", "lobster.conf"} <= set(outer_files)
    assert outer_files["CLAUDE.md"] == b"# recipes-tools\nrecipes-tools is public.\n"
    assert checkout_files["LICENSE"] == b"MIT 2026\n"
    assert "recipes-tools/CLAUDE.md" not in outer_files and "CLAUDE.md" not in checkout_files
    inits = [c["cwd"] for c in world.calls() if c["prog"] == "git" and c["args"][:1] == ["init"]]
    assert inits == [os.path.join(world.non_code, "recipes"), checkout]
    backlogs = [c["cwd"] for c in world.calls() if c["prog"] == "backlog"]
    assert backlogs == [os.path.join(world.non_code, "recipes"), outer]
    adds = [c for c in world.calls() if c["prog"] == "git" and c["args"][:1] == ["add"]]
    assert adds[1]["cwd"] == checkout and "backlog" not in adds[1]["args"] and "LICENSE" in adds[1]["args"]
    assert "(public)" in out


def test_a_failing_program_stops_with_exit_5_saying_what_failed_and_what_was_made(world):
    world.fail("backlog")
    code, out, err = world.run("recipes")
    assert code == 5
    nc, tools = made(world)
    assert err.startswith("new-lobster: backlog init recipes failed (exit 1) in %s\n" % nc)
    assert "Already made, and left as it is: %s, %s" % (nc, tools) in err
    assert os.path.isfile(os.path.join(nc, "CLAUDE.md"))
    assert [c["prog"] for c in world.calls()][-1] == "backlog"


def test_the_template_is_byte_for_byte_unchanged_after_a_run(world):
    before = tree(world.template)
    world.run("recipes")
    assert tree(world.template) == before


def test_model_and_effort_come_from_the_settings_or_the_flags(world):
    world.write_conf("MODEL=sonnet\n")
    world.run("--effort", "max", "recipes")
    conf = tree(os.path.join(world.non_code, "recipes"))["lobster.conf"]
    assert conf == b"KIND=non-code\nMODEL=sonnet\nEFFORT=max\n"


def test_without_a_settings_file_the_defaults_are_used_and_a_missing_lobster_mail_is_a_plain_error(world):
    os.remove(world.conf)
    code, out, err = world.run("recipes")
    assert code == 5
    assert err.startswith("new-lobster: lobster-mail duty status --all could not be run in ")
    assert "Traceback" not in err
    assert os.listdir(world.non_code) == []


def test_unexpected_output_from_the_mailbox_listing_is_a_plain_error(world):
    with open(os.path.join(world.bin, "duty.json"), "w") as f:
        f.write("not json")
    code, out, err = world.run("recipes")
    assert code == 5
    assert err == "new-lobster: lobster-mail duty status --all --json did not print the expected JSON\n"


def test_a_template_without_a_common_file_is_refused_with_exit_4(world):
    os.remove(os.path.join(world.template, "common", "lobster.conf"))
    code, out, err = world.run("recipes")
    assert code == 4
    assert err == "new-lobster: the template cannot be used: the template has no common/lobster.conf\n"


def test_the_command_file_runs_as_a_program(tmp_path):
    import subprocess
    import sys
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    done = subprocess.run([sys.executable, os.path.join(here, "new-lobster"), "--help"],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                          env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("usage: new-lobster")


def test_paths_with_quotes_dollars_and_non_ascii_letters_are_data_never_code(world):
    odd = os.path.join(world.home, "it's $HOME \"code\" — ünïcode")
    os.makedirs(odd)
    code, out, err = world.run("--code-dir", odd, "recipes")
    assert code == 0, err
    tools = os.path.join(odd, "recipes-tools")
    assert os.path.isfile(os.path.join(tools, "CLAUDE.md"))
    assert "git -C '%s' push -u origin main" % tools.replace("'", "'\"'\"'") in out
    assert {c["cwd"] for c in world.calls() if c["prog"] == "git"} >= {tools}


def test_no_name_or_an_unknown_flag_is_refused_with_exit_2(world):
    assert world.run() == (2, "", "new-lobster: the following arguments are required: name "
                                  "(new-lobster --help shows the form)\n")
    code, out, err = world.run("--colour", "recipes")
    assert code == 2 and err == "new-lobster: unrecognized arguments: --colour (new-lobster --help shows the form)\n"
