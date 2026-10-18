import pytest

from bernstein.settings import SettingsRefused, options_for_new_lobster, read_settings

HOME = "/home/sq"


def test_an_empty_file_gives_the_defaults_with_home_filled_in():
    assert read_settings("", HOME) == {
        "TEMPLATE": "/home/sq/projects/code/bernstein-code/templates/lobster",
        "NON_CODE_DIR": "/home/sq/projects/non-code",
        "CODE_DIR": "/home/sq/projects/code",
        "MODEL": "opus",
        "EFFORT": "high",
        "LOBSTER_MAIL": "/home/sq/projects/code/lobster-tools-code/lobster-tools/lobster-mail",
        "MAIL_ROOT": "/home/sq/projects/mail",
        "PYTHON": "/usr/bin/python3",
    }


def test_a_setting_overrides_its_default_and_comments_blank_lines_and_quotes_are_handled():
    text = "# my settings\n\nCODE_DIR = ~/work/code\nMODEL='sonnet'\nEFFORT=\"max\"\n"
    got = read_settings(text, HOME)
    assert (got["CODE_DIR"], got["MODEL"], got["EFFORT"]) == ("/home/sq/work/code", "sonnet", "max")
    assert got["NON_CODE_DIR"] == "/home/sq/projects/non-code"


def test_a_path_with_spaces_and_non_ascii_letters_is_kept_whole():
    got = read_settings('TEMPLATE="~/My Drive/modèles"\n', HOME)
    assert got["TEMPLATE"] == "/home/sq/My Drive/modèles"


@pytest.mark.parametrize(
    "text, why",
    [
        ("CODE_DIR=~/x\nFOO=1\n", "line 2: unknown setting FOO"),
        ("just words\n", "line 1: not a KEY=value line: just words"),
        ("EFFORT=extreme\n", "line 1: EFFORT must be one of low, medium, high, xhigh, max"),
        ("MODEL=\n", "line 1: MODEL is empty"),
        ("MODEL=opus 5\n", "line 1: MODEL must be one word, such as opus or sonnet"),
    ],
)
def test_refuses_a_bad_settings_line_naming_it(text, why):
    with pytest.raises(SettingsRefused) as refused:
        read_settings(text, HOME)
    assert str(refused.value) == why


def test_the_name_and_the_settings_make_the_options():
    o = options_for_new_lobster(["recipes"], read_settings("", HOME))
    assert (o.name, o.public, o.dry_run, o.model, o.effort) == ("recipes", False, False, "opus", "high")
    assert o.code_dir == "/home/sq/projects/code"


def test_flags_win_over_settings():
    settings = read_settings("MODEL=sonnet\nCODE_DIR=~/a\n", HOME)
    o = options_for_new_lobster(
        ["--public", "--dry-run", "--model", "opus", "--effort", "low", "--code-dir", "/b",
         "--non-code-dir", "/c", "--template", "/t", "recipes"], settings)
    assert (o.public, o.dry_run, o.model, o.effort) == (True, True, "opus", "low")
    assert (o.code_dir, o.non_code_dir, o.template) == ("/b", "/c", "/t")


def test_refuses_a_bad_effort_flag():
    with pytest.raises(SettingsRefused) as refused:
        options_for_new_lobster(["--effort", "huge", "recipes"], read_settings("", HOME))
    assert str(refused.value) == "--effort must be one of low, medium, high, xhigh, max"


def test_refuses_a_bad_name_with_the_rule():
    with pytest.raises(SettingsRefused) as refused:
        options_for_new_lobster(["Recipes"], read_settings("", HOME))
    assert str(refused.value) == "the name Recipes cannot be used: use only lower-case letters, digits and hyphens"


def test_an_absolute_path_is_kept_as_it_is():
    assert read_settings("CODE_DIR=/srv/code\n", HOME)["CODE_DIR"] == "/srv/code"
