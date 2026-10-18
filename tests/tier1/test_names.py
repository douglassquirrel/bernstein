import pytest

from bernstein.names import NameRefused, check_name


@pytest.mark.parametrize("name", ["recipes", "audio-description", "a1", "ab", "x" * 40, "a-b-c"])
def test_accepts_lower_case_names_with_single_hyphens(name):
    assert check_name(name) is None


@pytest.mark.parametrize(
    "name, why",
    [
        ("", "the name is empty"),
        ("a", "the name must be 2 to 40 characters long"),
        ("x" * 41, "the name must be 2 to 40 characters long"),
        ("Recipes", "use only lower-case letters, digits and hyphens"),
        ("rec ipes", "use only lower-case letters, digits and hyphens"),
        ("récipes", "use only lower-case letters, digits and hyphens"),
        ("../recipes", "use only lower-case letters, digits and hyphens"),
        ("rec_ipes", "use only lower-case letters, digits and hyphens"),
        ("1recipes", "the name must start with a letter"),
        ("-recipes", "the name must start with a letter"),
        ("recipes-", "the name must not end with a hyphen"),
        ("rec--ipes", "use single hyphens only"),
        ("recipes-tools", "the name must not end in -tools: new-lobster adds -tools for the tools project"),
    ],
)
def test_refuses_a_name_that_breaks_a_rule_saying_which(name, why):
    with pytest.raises(NameRefused) as refused:
        check_name(name)
    assert str(refused.value) == why
