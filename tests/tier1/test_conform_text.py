import json

from bernstein.conform import hook_has_root


def hook(root_word):
    """A hook's JSON text, with the shell word for the mail root written as the template writes it."""
    command = f'"$HOME/l/lobster-mail" start --project "$CLAUDE_PROJECT_DIR" --root {root_word}'
    return json.dumps({"command": command}, ensure_ascii=False)


def test_a_plain_root_is_found_as_one_word():
    assert hook_has_root(hook("/home/sq/mail"), "/home/sq/mail")


def test_a_root_is_not_found_inside_a_longer_path():
    assert not hook_has_root(hook("/home/sq/mail2"), "/home/sq/mail")


def test_a_root_needing_shell_quotes_must_be_quoted_in_the_hook():
    assert hook_has_root(hook("'/home/s q/mail'"), "/home/s q/mail")
    assert not hook_has_root(hook("/home/s q/mail"), "/home/s q/mail")


def test_a_root_with_quotes_backslashes_a_dollar_and_non_ascii_is_matched_exactly():
    root = '/home/"sq"/a\\b/$x/café</script>'
    word = "'" + root + "'"
    assert hook_has_root(hook(word), root)


def test_a_hook_with_no_root_has_none():
    assert not hook_has_root('{"command": "lobster-mail start --project x"}', "/home/sq/mail")
