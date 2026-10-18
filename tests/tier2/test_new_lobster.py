import os

from conftest import tree


def test_help_describes_the_command_and_exits_0(world):
    code, out, _err = world.run("--help")
    assert code == 0
    assert "usage: new-lobster" in out and "--dry-run" in out and "--public" in out
    assert world.calls() == []


def test_a_bad_name_is_refused_with_exit_2_and_nothing_is_touched(world):
    code, _out, err = world.run("Recipes")
    assert code == 2
    assert err == ("new-lobster: the name Recipes cannot be used: use only lower-case letters, "
                   "digits and hyphens (new-lobster --help shows the form)\n")
    assert world.calls() == [] and os.listdir(world.non_code) == [] and os.listdir(world.code) == []


def test_a_bad_settings_line_is_refused_with_exit_2_naming_the_file(world):
    world.write_conf("EFFORT=extreme\n")
    code, _out, err = world.run("recipes")
    assert code == 2
    assert err == f"new-lobster: {world.conf}: line 7: EFFORT must be one of low, medium, high, xhigh, max\n"


def test_an_existing_folder_is_refused_with_exit_3_and_left_exactly_as_it_was(world):
    existing = os.path.join(world.code, "recipes-tools")
    os.makedirs(existing)
    with open(os.path.join(existing, "keep.txt"), "w") as f:
        f.write("mine\n")
    before = tree(world.code), tree(world.template)
    code, _out, err = world.run("recipes")
    assert code == 3
    assert err == f"new-lobster: {existing} already exists; nothing was made\n"
    assert (tree(world.code), tree(world.template)) == before
    assert not os.path.exists(os.path.join(world.non_code, "recipes"))
    assert world.calls() == []


def test_an_existing_mailbox_is_refused_with_exit_3(world):
    world.mailboxes(["recipes"])
    code, _out, err = world.run("recipes")
    assert code == 3
    assert err == f"new-lobster: the mailbox recipes already exists in {world.mail}; nothing was made\n"
    assert os.listdir(world.non_code) == []


def test_a_folder_of_that_name_in_the_mail_root_counts_as_in_the_way(world):
    world.mailboxes([], skipped=["recipes-tools"])
    code, _out, err = world.run("recipes")
    assert code == 3
    assert "the mailbox recipes-tools already exists" in err


def test_a_template_with_an_unknown_placeholder_is_refused_with_exit_4_before_anything_is_written(world):
    with open(os.path.join(world.template, "code", "PLAN.md"), "w") as f:
        f.write("{{WHO}}\n")
    code, _out, err = world.run("recipes")
    assert code == 4
    assert err == "new-lobster: the template cannot be used: code/PLAN.md: unknown placeholder {{WHO}}\n"
    assert os.listdir(world.non_code) == [] and os.listdir(world.code) == []


def test_a_missing_template_is_refused_with_exit_4(world):
    code, _out, err = world.run("--template", os.path.join(world.home, "nowhere"), "recipes")
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
    code, _out, err = world.run("recipes")
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
    code, _out, err = world.run("recipes")
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
                     "--task-prefix", "re", "--zero-padded-ids", "3"], nc),
        ("backlog", ["init", "recipes-tools", "--defaults", "--no-git", "--integration-mode", "none",
                     "--task-prefix", "re", "--zero-padded-ids", "3"], tools),
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
    _code, out, _err = world.run("recipes")
    nc, tools = made(world)
    assert f"Made recipes: {nc}" in out
    assert f"Made recipes-tools: {tools}" in out
    assert f"Mailboxes recipes and recipes-tools in {world.mail}" in out
    assert "git@github.com:douglassquirrel/recipes.git" in out
    assert "git@github.com:douglassquirrel/recipes-tools.git" in out
    assert f"git -C '{nc}' push -u origin main" in out
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
    code, _out, err = world.run("recipes")
    assert code == 5
    nc, tools = made(world)
    assert err.startswith(f"new-lobster: backlog init recipes failed (exit 1) in {nc}\n")
    assert f"Already made, and left as it is: {nc}, {tools}" in err
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
    code, _out, err = world.run("recipes")
    assert code == 5
    assert err.startswith("new-lobster: lobster-mail duty status --all could not be run in ")
    assert "Traceback" not in err
    assert os.listdir(world.non_code) == []


def test_unexpected_output_from_the_mailbox_listing_is_a_plain_error(world):
    with open(os.path.join(world.bin, "duty.json"), "w") as f:
        f.write("not json")
    code, _out, err = world.run("recipes")
    assert code == 5
    assert err == "new-lobster: lobster-mail duty status --all --json did not print the expected JSON\n"


def test_a_template_without_a_common_file_is_refused_with_exit_4(world):
    os.remove(os.path.join(world.template, "common", "lobster.conf"))
    code, _out, err = world.run("recipes")
    assert code == 4
    assert err == "new-lobster: the template cannot be used: the template has no common/lobster.conf\n"


def test_the_command_file_runs_as_a_program(tmp_path):
    import subprocess
    import sys
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    done = subprocess.run([sys.executable, os.path.join(here, "new-lobster"), "--help"],
                          capture_output=True, text=True, check=False,
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
    assert "git -C '{}' push -u origin main".format(tools.replace("'", "'\"'\"'")) in out
    assert {c["cwd"] for c in world.calls() if c["prog"] == "git"} >= {tools}


def test_no_name_or_an_unknown_flag_is_refused_with_exit_2(world):
    assert world.run() == (2, "", ("new-lobster: the following arguments are required: name "
                                  "(new-lobster --help shows the form)\n"))
    code, _out, err = world.run("--colour", "recipes")
    assert code == 2 and err == "new-lobster: unrecognized arguments: --colour (new-lobster --help shows the form)\n"


def test_render_into_writes_both_halves_into_the_folder_and_nothing_else(world, tmp_path):
    out_dir = str(tmp_path / "rendered")
    code, out, err = world.run("--render-into", out_dir, "recipes")
    assert (code, err) == (0, "")
    files = tree(out_dir)
    assert files["non-code/START-HERE.txt"] == b"Start recipes on 18 October 2026.\n"
    assert files["code/CLAUDE.md"] == b"# recipes-tools\nrecipes-tools is private.\n"
    assert files["code/recipes-tools.conf.example"] == b"# ~/.recipes-tools.conf\n"
    assert sorted(files) == sorted(["non-code/CLAUDE.md", "non-code/START-HERE.txt", "non-code/.gitignore",
                                    "non-code/inbox/README.md", "non-code/lobster.conf", "code/CLAUDE.md",
                                    "code/START-HERE.txt", "code/PLAN.md", "code/pyproject.toml",
                                    "code/requirements-dev.txt", "code/recipes-tools.conf.example",
                                    "code/inbox/README.md", "code/lobster.conf"])
    assert world.calls() == [] and os.listdir(world.non_code) == [] and os.listdir(world.code) == []
    assert out == f"Rendered the template for recipes and recipes-tools into {out_dir}: 13 files. Nothing else was written.\n"


def test_render_into_refuses_a_folder_that_exists_and_leaves_it_as_it_was(world, tmp_path):
    out_dir = tmp_path / "rendered"
    out_dir.mkdir()
    (out_dir / "keep.txt").write_text("mine\n")
    code, out, err = world.run("--render-into", str(out_dir), "recipes")
    assert (code, out, err) == (3, "", f"new-lobster: {out_dir} already exists; nothing was written\n")
    assert tree(str(out_dir)) == {"keep.txt": b"mine\n"}


def test_render_into_takes_the_pairs_own_tools_name_and_folders(world, tmp_path):
    with open(os.path.join(world.template, "non-code", "paths.txt"), "w") as f:
        f.write("{{SISTER}} at {{TOOLS_PATH}}; {{NAME}} at {{NONCODE_PATH}}\n")
    out_dir = str(tmp_path / "rendered")
    nc = os.path.join(world.home, "projects", "non-code", "videos", "training-video")
    tools = os.path.join(world.home, "projects", "code", "videos", "video-tools-code", "video-tools")
    code, _out, err = world.run("--render-into", out_dir, "--tools", "video-tools", "--non-code-path", nc,
                                "--tools-path", tools, "--public", "training-video")
    assert (code, err) == (0, "")
    files = tree(out_dir)
    assert files["non-code/paths.txt"] == (b"video-tools at ~/projects/code/videos/video-tools-code/video-tools; "
                                           b"training-video at ~/projects/non-code/videos/training-video\n")
    assert files["code/CLAUDE.md"] == b"# video-tools\nvideo-tools is public.\n"
    assert "code/video-tools.conf.example" in files and "code/LICENSE" in files


def test_render_into_refuses_a_bad_tools_name_and_the_pair_flags_alone(world, tmp_path):
    out_dir = str(tmp_path / "rendered")
    code, _out, err = world.run("--render-into", out_dir, "--tools", "videos", "training-video")
    assert (code, err) == (2, "new-lobster: the tools name videos must end in -tools (new-lobster --help shows the form)\n")
    code, _out, err = world.run("--render-into", out_dir, "--tools", "Bad Name-tools", "training-video")
    assert code == 2 and err.startswith("new-lobster: the tools name Bad Name-tools cannot be used: ")
    for flag in ("--tools", "--non-code-path", "--tools-path"):
        code, _out, err = world.run(flag, "x-tools", "recipes")
        assert (code, err) == (2, f"new-lobster: {flag} needs --render-into (new-lobster --help shows the form)\n")
    assert not os.path.exists(out_dir) and world.calls() == []


def test_render_into_dry_run_lists_the_files_and_writes_nothing(world, tmp_path):
    out_dir = str(tmp_path / "rendered")
    code, out, err = world.run("--render-into", out_dir, "--dry-run", "recipes")
    assert (code, err) == (0, "")
    assert out.startswith(f"Would render the template for recipes and recipes-tools into {out_dir}: 13 files\n"
                          "  code/CLAUDE.md\n")
    assert "  non-code/START-HERE.txt\n" in out and out.endswith("Dry run: nothing was written.\n")
    assert not os.path.exists(out_dir) and world.calls() == []


def test_render_into_refuses_a_template_with_an_unknown_placeholder_and_writes_nothing(world, tmp_path):
    with open(os.path.join(world.template, "code", "PLAN.md"), "w") as f:
        f.write("{{NOT_A_PLACEHOLDER}}\n")
    out_dir = str(tmp_path / "rendered")
    code, out, err = world.run("--render-into", out_dir, "recipes")
    assert code == 4 and out == "" and err.startswith("new-lobster: the template cannot be used: ")
    assert not os.path.exists(out_dir)
