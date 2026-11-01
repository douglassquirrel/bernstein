import datetime

import pytest

from bernstein.render import TemplateRefused, fill, render_half, values_for

VALUES = {"NAME": "recipes", "TOOLS": "recipes-tools", "SELF": "recipes", "VISIBILITY": "private"}


def write(root, files):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def test_fill_replaces_known_placeholders_and_leaves_the_rest_as_written():
    text = "{{NAME}} and {{TOOLS}}; {{to fill: the purpose}}; on {{D Month YYYY}}; {{not caps}}\n"
    assert fill(text, VALUES, "x.md") == (
        "recipes and recipes-tools; {{to fill: the purpose}}; on {{D Month YYYY}}; {{not caps}}\n")


def test_fill_refuses_an_unknown_capitals_placeholder_naming_the_file():
    with pytest.raises(TemplateRefused) as refused:
        fill("a {{NAME}} b {{WHO}}\n", VALUES, "non-code/CLAUDE.md")
    assert str(refused.value) == "non-code/CLAUDE.md: unknown placeholder {{WHO}}"


def template(tmp_path):
    write(tmp_path, {
        "common/sections/rule.md": "Rule for {{SELF}}.\nSecond line.\n",
        "common/sections/repo-private.md": "A private {{TOOLS}}.\n",
        "common/sections/repo-public.md": "A public {{TOOLS}}.\n",
        "common/inbox/README.md": "Inbox of {{SELF}}.\n",
        "common/lobster.conf": "SELF={{SELF}}\n",
        "non-code/CLAUDE.md": "# {{NAME}}\n\n{{> sections/rule.md}}\n\nEnd.\n",
        "non-code/.claude/settings.json": "{}\n",
        "code/CLAUDE.md": "# {{TOOLS}}\n{{> sections/repo-{{VISIBILITY}}.md}}\n",
        "code/LICENSE": "MIT\n",
        "code/tools.conf.example": "# {{TOOLS}}\n",
    })
    return tmp_path


def test_render_half_gives_the_half_its_own_files_and_the_common_ones_with_includes_resolved(tmp_path):
    got = render_half(str(template(tmp_path)), "non-code", VALUES, public=False)
    assert got == {
        "CLAUDE.md": "# recipes\n\nRule for recipes.\nSecond line.\n\nEnd.\n",
        ".claude/settings.json": "{}\n",
        "inbox/README.md": "Inbox of recipes.\n",
        "lobster.conf": "SELF=recipes\n",
    }


def test_a_private_tools_half_gets_the_private_paragraph_no_licence_and_a_renamed_conf_example(tmp_path):
    values = dict(VALUES, SELF="recipes-tools")
    got = render_half(str(template(tmp_path)), "code", values, public=False)
    assert got["CLAUDE.md"] == "# recipes-tools\nA private recipes-tools.\n"
    assert "LICENSE" not in got
    assert got["recipes-tools.conf.example"] == "# recipes-tools\n"
    assert "tools.conf.example" not in got


def test_a_public_tools_half_gets_the_public_paragraph_and_the_licence(tmp_path):
    values = dict(VALUES, SELF="recipes-tools", VISIBILITY="public")
    got = render_half(str(template(tmp_path)), "code", values, public=True)
    assert got["CLAUDE.md"] == "# recipes-tools\nA public recipes-tools.\n"
    assert got["LICENSE"] == "MIT\n"


def test_refuses_a_missing_include_naming_the_file_and_the_include(tmp_path):
    t = template(tmp_path)
    (t / "non-code" / "CLAUDE.md").write_text("{{> sections/nowhere.md}}\n", encoding="utf-8")
    with pytest.raises(TemplateRefused) as refused:
        render_half(str(t), "non-code", VALUES, public=False)
    assert str(refused.value) == "non-code/CLAUDE.md: the include sections/nowhere.md is not in common/"


def test_refuses_a_missing_template_folder(tmp_path):
    with pytest.raises(TemplateRefused) as refused:
        render_half(str(tmp_path / "gone"), "non-code", VALUES, public=False)
    assert str(refused.value) == "the template folder %s has no non-code/ folder" % (tmp_path / "gone")


def test_values_for_each_half():
    common = {"model": "opus", "effort": "high", "non_code_dir": "/h/projects/non-code", "code_dir": "/h/projects/code",
                  "mail_root": "/h/projects/mail", "lobster_mail": "/h/l/lobster-tools/lobster-mail",
                  "today": datetime.date(2026, 10, 8), "home": "/h"}
    nc = values_for("recipes", "non-code", public=False, **common)
    pinned = {
        "NAME": "recipes", "TOOLS": "recipes-tools", "SELF": "recipes", "SISTER": "recipes-tools",
        "KIND": "non-code", "PACKAGE": "recipestools", "DATE": "8 October 2026", "YEAR": "2026",
        "MODEL": "Opus", "MODEL_SETTING": "opus", "EFFORT": "high",
        "NONCODE_PATH": "~/projects/non-code/recipes", "TOOLS_PATH": "~/projects/code/recipes-tools",
        "MAIL_ROOT": "~/projects/mail", "MAIL_ROOT_SHELL": "/h/projects/mail",
        "LOBSTER_TOOLS": "~/l/lobster-tools", "VISIBILITY": "private",
        "BACKLOG_PREFIX": "RE", "QUESTIONS_AT": 'CLAUDE.md, "Open questions for Squirrel"',
    }
    assert {k: nc[k] for k in pinned} == pinned  # the claw placeholders have their own test below
    code = values_for("recipes", "code", public=True, **common)
    assert (code["SELF"], code["SISTER"], code["KIND"], code["VISIBILITY"]) == ("recipes-tools", "recipes", "code", "public")
    assert code["TOOLS_PATH"] == "~/projects/code/recipes-tools-code/recipes-tools"
    assert code["QUESTIONS_AT"] == 'PLAN.md, "Open questions"'


def test_the_mail_root_for_the_shell_is_quoted_only_when_it_must_be():
    common = {"model": "opus", "effort": "high", "non_code_dir": "/h/n", "code_dir": "/h/c",
                  "lobster_mail": "/h/l/lobster-mail", "today": datetime.date(2026, 10, 8), "home": "/h"}
    got = values_for("recipes", "code", public=False, mail_root="/h/my mail", **common)
    assert got["MAIL_ROOT_SHELL"] == "'/h/my mail'"


def test_a_json_file_that_is_not_valid_once_filled_in_is_refused(tmp_path):
    t = template(tmp_path)
    (t / "non-code" / ".claude" / "settings.json").write_text('{"command": "start --as {{NAME}}"\n', encoding="utf-8")
    with pytest.raises(TemplateRefused) as refused:
        render_half(str(t), "non-code", VALUES, public=False)
    assert str(refused.value) == "non-code/.claude/settings.json: not valid JSON once filled in"


def test_values_for_an_existing_pair_take_its_own_tools_name_and_paths():
    common = {"model": "opus", "effort": "high", "non_code_dir": "/h/projects/non-code", "code_dir": "/h/projects/code",
              "mail_root": "/h/projects/mail", "lobster_mail": "/h/l/lobster-tools/lobster-mail",
              "today": datetime.date(2026, 10, 8), "home": "/h", "tools": "video-tools",
              "non_code_path": "/h/projects/non-code/videos/training-video",
              "tools_path": "/h/projects/code/videos/video-tools-code/video-tools"}
    nc = values_for("training-video", "non-code", public=True, **common)
    assert (nc["TOOLS"], nc["SISTER"], nc["PACKAGE"], nc["NONCODE_PATH"], nc["TOOLS_PATH"]) == (
        "video-tools", "video-tools", "videotools", "~/projects/non-code/videos/training-video",
        "~/projects/code/videos/video-tools-code/video-tools")
    code = values_for("training-video", "code", public=True, **common)
    assert (code["SELF"], code["SISTER"], code["BACKLOG_PREFIX"]) == ("video-tools", "training-video", "TR")


COMMON = {"model": "opus", "effort": "high", "non_code_dir": "/h/projects/non-code", "code_dir": "/h/projects/code",
          "mail_root": "/h/projects/mail", "lobster_mail": "/h/l/lobster-tools/lobster-mail",
          "today": datetime.date(2026, 11, 1), "home": "/h"}


def test_values_for_a_non_code_project_name_its_home_claw_and_the_further_claws_it_uses():
    nc = values_for("beyond-ai", "non-code", public=True, tools="book-tools",
                    claws=["word-tools", "google-docs-tools"], **COMMON)
    assert nc["CLAWS"] == "word-tools google-docs-tools"
    assert nc["CLAW_LIST"] == "`book-tools`, `word-tools` and `google-docs-tools`"
    assert nc["CLAW_NAMES"] == "book-tools, word-tools and google-docs-tools"
    assert nc["OTHER_CLAWS"] == "It also uses the claws `word-tools` and `google-docs-tools`."
    assert nc["CLAW_MOUNTS"] == (
        "| `~/mnt/book-tools` | the home claw, `book-tools`: **read and run only**; never write, commit, install or make a `.venv` in it |\n"
        "| `~/mnt/word-tools` | the claw `word-tools`: read and run only, as above |\n"
        "| `~/mnt/google-docs-tools` | the claw `google-docs-tools`: read and run only, as above |")
    assert nc["CLAW_ROWS"] == (
        "| `book-tools` | {{to fill: as they are made}} | From `~/mnt/book-tools`, as its README says; the home claw, where new tools are born |\n"
        "| `word-tools` | {{to fill: as they are used}} | From `~/mnt/word-tools`, as its README says |\n"
        "| `google-docs-tools` | {{to fill: as they are used}} | From `~/mnt/google-docs-tools`, as its README says |")
    alone = values_for("recipes", "non-code", public=False, **COMMON)
    assert (alone["CLAWS"], alone["CLAW_LIST"], alone["CLAW_NAMES"]) == ("", "`recipes-tools`", "recipes-tools")
    assert alone["OTHER_CLAWS"] == "It uses no other claw yet; when it comes to, `CLAWS` in `lobster.conf` names them."
    assert alone["CLAW_MOUNTS"].count("\n") == 0 and alone["CLAW_ROWS"].count("\n") == 0


def test_values_for_a_pair_s_code_half_name_the_sister_where_a_lone_claw_names_any_project():
    pair = values_for("recipes", "code", public=False, **COMMON)
    assert pair["SERVED"] == "sister"
    assert pair["FOR_WHOM"] == "the work done in the sister project, `recipes` (`~/projects/non-code/recipes`)"
    assert (pair["REQUESTER"], pair["SERVING"]) == ("`recipes`", "`recipes`")
    assert (pair["TALKS_TO"], pair["ASKING"], pair["SEND_TO"]) == ("its sister project, `recipes`", "`recipes`", "recipes")
    assert pair["OF_WHOM"] == "the tools project of the lobster pair `recipes` and `recipes-tools`"
    assert pair["SISTER_FIRST_SESSION"].startswith("In this tools half, read the sister project's CLAUDE.md first (read only:\n"
                                                   "   ~/projects/non-code/recipes/CLAUDE.md,")
    lone = values_for(None, "code", public=True, tools="word-tools", **COMMON)
    assert (lone["NAME"], lone["SISTER"], lone["NONCODE_PATH"], lone["SELF"], lone["TOOLS"]) == (
        "", "", "", "word-tools", "word-tools")
    assert (lone["SERVED"], lone["BACKLOG_PREFIX"], lone["PACKAGE"], lone["KIND"]) == ("any", "WO", "wordtools", "code")
    assert lone["TOOLS_PATH"] == "~/projects/code/word-tools-code/word-tools"
    assert lone["FOR_WHOM"] == ("the work done in Squirrel's lobster projects (the ganglia), any of which may ask this "
                                "claw for a tool")
    assert (lone["REQUESTER"], lone["SERVING"]) == ("a lobster project", "Squirrel's lobster projects")
    assert (lone["TALKS_TO"], lone["ASKING"], lone["SEND_TO"]) == ("the lobster projects it serves", "another project", "<project>")
    assert lone["OF_WHOM"] == "a claw, `word-tools`: a tools project with no sister project, used by any lobster project that asks"
    assert lone["SISTER_FIRST_SESSION"].startswith("This claw has no sister project: ask Squirrel which lobster projects will use it first")
    assert lone["CLAWS"] == ""


def test_the_sister_words_of_a_non_code_half_name_its_tools_project_not_itself():
    nc = values_for("training-video", "non-code", public=True, tools="video-tools", **COMMON)
    assert (nc["TALKS_TO"], nc["ASKING"], nc["SEND_TO"]) == ("its sister project, `video-tools`", "`video-tools`", "video-tools")
    code = values_for("training-video", "code", public=True, tools="video-tools", **COMMON)
    assert (code["TALKS_TO"], code["ASKING"], code["SEND_TO"]) == (
        "its sister project, `training-video`", "`training-video`", "training-video")
