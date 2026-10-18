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
    assert nc == {
        "NAME": "recipes", "TOOLS": "recipes-tools", "SELF": "recipes", "SISTER": "recipes-tools",
        "KIND": "non-code", "PACKAGE": "recipestools", "DATE": "8 October 2026", "YEAR": "2026",
        "MODEL": "Opus", "MODEL_SETTING": "opus", "EFFORT": "high",
        "NONCODE_PATH": "~/projects/non-code/recipes", "TOOLS_PATH": "~/projects/code/recipes-tools",
        "MAIL_ROOT": "~/projects/mail", "LOBSTER_TOOLS": "~/l/lobster-tools", "VISIBILITY": "private",
        "BACKLOG_PREFIX": "RE", "QUESTIONS_AT": 'CLAUDE.md, "Open questions for Squirrel"',
    }
    code = values_for("recipes", "code", public=True, **common)
    assert (code["SELF"], code["SISTER"], code["KIND"], code["VISIBILITY"]) == ("recipes-tools", "recipes", "code", "public")
    assert code["TOOLS_PATH"] == "~/projects/code/recipes-tools-code/recipes-tools"
    assert code["QUESTIONS_AT"] == 'PLAN.md, "Open questions"'
