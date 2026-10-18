import datetime
import os
from urllib.parse import quote as urlquote

import pytest

from bernstein.conduct import ProjectRefused, find_project, link_for, start_message, stop_message

DAY = datetime.date(2026, 10, 18)


def quote(text):
    return urlquote(text, safe="")


def test_the_start_message_points_to_start_here_and_waits_without_a_brief():
    assert start_message(None, DAY) == (
        "Start (from bernstein, 18 October 2026).\n\n"
        "Squirrel has started this session through bernstein. Follow START-HERE.txt in this\n"
        "project's folder from the top: step 0 (the model and effort question) first, then the\n"
        "mail and the rest.\n\n"
        "Then wait for Squirrel.\n")


def test_the_start_message_carries_the_brief_word_for_word():
    text = start_message("Draft the menu for Sunday.\nKeep it vegetarian.\n", DAY)
    assert text.endswith("Then this brief, from Squirrel:\n\nDraft the menu for Sunday.\nKeep it vegetarian.\n")


def test_the_stop_message_asks_for_a_handover_at_a_safe_point():
    assert stop_message(DAY) == (
        "Stop (from bernstein, 18 October 2026).\n\n"
        "Squirrel has asked this session to hand over and stop. At the next safe point (nothing\n"
        "half-edited, nothing half-committed): bring the record up to date, send the handover with\n"
        "lobster-mail handover, stop watching mail and stop the check-in chain, tell Squirrel in\n"
        "chat that bernstein asked you to hand over, and do nothing more unless he says.\n")


def make(tmp_path, rel, kind, sister):
    folder = tmp_path / rel
    folder.mkdir(parents=True)
    (folder / "lobster.conf").write_text(f"KIND={kind}\nSISTER={sister}\nMODEL=opus\nEFFORT=high\n")
    (folder / "START-HERE.txt").write_text("Start.\n")
    return str(folder)


def test_find_project_for_each_kind_and_layout(tmp_path):
    nc = make(tmp_path, "non-code/recipes", "non-code", "recipes-tools")
    tools = make(tmp_path, "code/recipes-tools", "code", "recipes")
    p = find_project("recipes", str(tmp_path / "non-code"), str(tmp_path / "code"))
    assert (p.name, p.kind, p.folder, p.sister, p.sister_checkout) == ("recipes", "non-code", nc, "recipes-tools", tools)
    q = find_project("recipes-tools", str(tmp_path / "non-code"), str(tmp_path / "code"))
    assert (q.kind, q.folder, q.checkout) == ("code", tools, tools)


def test_find_project_for_a_public_tools_project(tmp_path):
    outer = make(tmp_path, "code/pub-tools-code", "code", "pub")
    os.makedirs(os.path.join(outer, "pub-tools"))
    make(tmp_path, "non-code/pub", "non-code", "pub-tools")
    q = find_project("pub-tools", str(tmp_path / "non-code"), str(tmp_path / "code"))
    assert (q.folder, q.checkout) == (outer, os.path.join(outer, "pub-tools"))
    p = find_project("pub", str(tmp_path / "non-code"), str(tmp_path / "code"))
    assert p.sister_checkout == os.path.join(outer, "pub-tools")


def test_find_project_refuses_a_project_with_no_folder_or_no_settings(tmp_path):
    with pytest.raises(ProjectRefused) as refused:
        find_project("nope", str(tmp_path / "non-code"), str(tmp_path / "code"))
    assert str(refused.value) == "no project nope in %s or a folder directly inside it" % (tmp_path / "non-code")
    os.makedirs(tmp_path / "non-code" / "bare")
    with pytest.raises(ProjectRefused) as refused:
        find_project("bare", str(tmp_path / "non-code"), str(tmp_path / "code"))
    assert str(refused.value) == "%s has no lobster.conf: is it a lobster project?" % (tmp_path / "non-code" / "bare")


def test_the_link_for_a_non_code_project_connects_its_four_folders(tmp_path):
    make(tmp_path, "non-code/recipes", "non-code", "recipes-tools")
    make(tmp_path, "code/recipes-tools", "code", "recipes")
    p = find_project("recipes", str(tmp_path / "non-code"), str(tmp_path / "code"))
    link = link_for(p, "/m/mail", "/l/lobster-tools")
    enc = lambda s: s.replace("/", "%2F")
    assert link == ("claude://cowork/new?folder=" + enc(p.folder) + "&folder=%2Fm%2Fmail"
                    "&folder=" + enc(p.sister_checkout) + "&folder=%2Fl%2Flobster-tools"
                    "&q=" + quote("Read START-HERE.txt in the recipes folder (mounted at ~/mnt/recipes) and do "
                                  "what it says, starting with its step 0 before anything else. If ~/mnt/recipes "
                                  "is not there, say \"the app opened me without the recipes folder\" and stop."))


def test_the_link_for_a_tools_project_opens_claude_code_in_its_folder(tmp_path):
    make(tmp_path, "code/recipes-tools", "code", "recipes")
    q = find_project("recipes-tools", str(tmp_path / "non-code"), str(tmp_path / "code"))
    assert link_for(q, "/m/mail", "/l/lobster-tools") == (
        "claude://code/new?folder=" + quote(q.folder) + "&q=" + quote(
            "This session must work in " + q.folder + ". If your working folder is anything else, say \"the app "
            "opened me in the wrong folder\" and stop. Otherwise read START-HERE.txt there and do what it says, "
            "starting with its step 0 before anything else."))
