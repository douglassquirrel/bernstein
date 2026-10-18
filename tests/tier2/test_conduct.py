import os


def sent(world):
    return [c for c in world.calls() if c["prog"] == "lobster-mail" and c["args"][:1] == ["send"]]


def opened(world):
    return [c["args"] for c in world.calls() if c["prog"] == "open"]


def test_help_names_both_verbs_and_exits_0(world):
    code, out, _err = world.conduct("--help")
    assert code == 0 and "conduct start" in out and "conduct stop" in out


def test_no_verb_or_an_unknown_verb_is_refused_with_exit_2(world):
    assert world.conduct()[0] == 2
    code, _out, err = world.conduct("pause", "recipes")
    assert code == 2 and err.startswith("conduct: ")


def test_start_refuses_an_unknown_project_with_exit_3(world):
    world.duty({})
    code, _out, err = world.conduct("start", "recipes")
    assert code == 3
    assert err == "conduct: no project recipes: {} does not exist\n".format(os.path.join(world.non_code, "recipes"))


def test_start_refuses_a_project_without_a_mailbox_with_exit_3(world):
    world.project("recipes", "non-code")
    world.duty({})
    code, _out, err = world.conduct("start", "recipes")
    assert code == 3 and err == f"conduct: there is no mailbox recipes in {world.mail}\n"


def test_start_refuses_when_a_session_is_already_on_duty_and_sends_nothing(world):
    world.project("recipes", "non-code")
    world.duty({"recipes": "fresh"})
    code, _out, err = world.conduct("start", "recipes")
    assert code == 3
    assert err == ("conduct: a session is already running for recipes: mac has been on duty since "
                   "2026-10-18T09:00:00Z, last beat 2026-10-18T09:30:00Z\n")
    assert sent(world) == [] and opened(world) == []


def test_start_sends_the_start_message_as_bernstein_then_opens_the_session(world):
    nc = world.project("recipes", "non-code")
    tools = world.project("recipes-tools", "code")
    world.duty({"recipes": "stale", "recipes-tools": None})
    code, out, err = world.conduct("start", "recipes")
    assert code == 0, err
    (mail,) = sent(world)
    assert mail["args"] == ["send", "--as", "bernstein", "--to", "recipes", "--subject", "Start: recipes",
                            "--root", world.mail, "-"]
    assert mail["stdin"].startswith("Start (from bernstein, 18 October 2026).")
    (link,) = opened(world)
    assert link[0].startswith("claude://cowork/new?folder=" + nc.replace("/", "%2F").replace(" ", "%20"))
    assert tools.replace("/", "%2F").replace(" ", "%20") in link[0]
    assert "Sent the Start message to recipes" in out and "Opened a Claude session" in out
    progs = [c["prog"] for c in world.calls()]
    assert progs == ["lobster-mail", "lobster-mail", "open"]


def test_start_of_a_tools_project_says_who_sets_its_model_and_effort(world):
    world.project("recipes-tools", "code")
    world.duty({"recipes-tools": None})
    code, out, _err = world.conduct("start", "recipes-tools")
    assert code == 0
    assert opened(world)[0][0].startswith("claude://code/new?folder=")
    assert ("Ask a bernstein session in the desktop app to set its model and effort to opus, high." in out)


def test_start_sets_the_pace_first_and_carries_a_brief(world, tmp_path):
    world.project("recipes", "non-code")
    world.project("recipes-tools", "code")
    world.duty({"recipes": None})
    brief = tmp_path / "brief.md"
    brief.write_text("Plan Sunday's menu.\n", encoding="utf-8")
    code, _out, err = world.conduct("start", "recipes", "--pace", "relaxed", "--brief", str(brief))
    assert code == 0, err
    lm = [c["args"] for c in world.calls() if c["prog"] == "lobster-mail"]
    assert lm[1] == ["pace", "--as", "recipes", "relaxed", "--root", world.mail]
    assert sent(world)[0]["stdin"].endswith("Then this brief, from Squirrel:\n\nPlan Sunday's menu.\n")


def test_start_refuses_a_bad_pace_and_a_missing_brief_with_exit_2(world):
    assert world.conduct("start", "recipes", "--pace", "frantic")[0] == 2
    code, _out, err = world.conduct("start", "recipes", "--brief", "/nowhere/brief.md")
    assert code == 2 and err == "conduct: the brief /nowhere/brief.md cannot be read\n"


def test_start_dry_run_shows_the_message_and_link_and_sends_and_opens_nothing(world):
    world.project("recipes", "non-code")
    world.project("recipes-tools", "code")
    world.duty({"recipes": None})
    code, out, _err = world.conduct("start", "--dry-run", "recipes")
    assert code == 0
    assert "Start (from bernstein, 18 October 2026)." in out and "claude://cowork/new?" in out
    assert "Dry run: nothing was sent or opened." in out
    assert sent(world) == [] and opened(world) == []


def test_a_duty_caught_changing_is_looked_at_again_then_refused_with_exit_4(world):
    world.project("recipes", "non-code")
    world.duty({"recipes": "changing"})
    waits = []
    code, _out, err = world.conduct("start", "recipes", sleep=waits.append)
    assert code == 4 and waits == [1, 1, 1]
    assert err == "conduct: the duty of recipes kept changing while it was read; run conduct again\n"


def test_a_failing_send_or_open_is_exit_4(world):
    world.project("recipes", "non-code")
    world.project("recipes-tools", "code")
    world.duty({"recipes": None})
    world.fail("open")
    code, _out, err = world.conduct("start", "recipes")
    assert code == 4 and err.startswith("conduct: open failed (exit 1)")
    assert len(sent(world)) == 1


def test_stop_with_nobody_on_duty_sends_nothing_and_exits_0(world):
    world.duty({"recipes": None})
    code, out, _err = world.conduct("stop", "recipes")
    assert code == 0 and out == "Nobody is on duty for recipes: nothing to stop.\n"
    assert sent(world) == []


def test_stop_sends_the_stop_message_as_bernstein(world):
    world.duty({"recipes": "fresh"})
    code, out, _err = world.conduct("stop", "recipes")
    assert code == 0
    (mail,) = sent(world)
    assert mail["args"] == ["send", "--as", "bernstein", "--to", "recipes", "--subject", "Stop: hand over",
                            "--root", world.mail, "-"]
    assert mail["stdin"].startswith("Stop (from bernstein, 18 October 2026).")
    assert out == "Sent the Stop message to recipes.\n"


def test_stop_all_asks_every_session_on_duty_except_bernstein(world):
    world.duty({"bernstein": "fresh", "recipes": "fresh", "audio": "stale", "video-tools": "fresh", "old": None})
    code, _out, _err = world.conduct("stop", "--all")
    assert code == 0
    assert [m["args"][4] for m in sent(world)] == ["recipes", "video-tools"]


def test_stop_needs_a_project_or_all_but_not_both(world):
    assert world.conduct("stop")[0] == 2
    assert world.conduct("stop", "--all", "recipes")[0] == 2


def test_stop_wait_reports_the_handover_once_the_duty_is_given_up(world):
    world.duty({"recipes": "fresh"})
    looks = []

    def sleep(seconds):
        looks.append(seconds)
        if len(looks) == 2:
            world.duty({"recipes": "handed over"})

    code, out, _err = world.conduct("stop", "recipes", "--wait", "60", sleep=sleep)
    assert code == 0 and looks == [10, 10]
    assert out.endswith("recipes has handed over.\n")


def test_stop_wait_runs_out_with_exit_5_naming_who_is_still_on_duty(world):
    world.duty({"recipes": "fresh"})
    looks = []
    code, _out, err = world.conduct("stop", "recipes", "--wait", "30", sleep=looks.append)
    assert code == 5 and looks == [10, 10, 10]
    assert err == "conduct: after 30 seconds, still on duty: recipes\n"


def test_the_command_file_runs_as_a_program(tmp_path):
    import subprocess
    import sys
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    done = subprocess.run([sys.executable, os.path.join(here, "conduct"), "--help"], capture_output=True,
                          text=True, check=False, env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("usage: conduct")


def test_stop_refuses_an_unknown_mailbox_with_exit_3(world):
    world.duty({})
    code, _out, err = world.conduct("stop", "recipes")
    assert code == 3 and err == f"conduct: there is no mailbox recipes in {world.mail}\n"


def test_stop_dry_run_shows_the_message_and_sends_nothing(world):
    world.duty({"recipes": "fresh"})
    code, out, _err = world.conduct("stop", "--dry-run", "recipes")
    assert code == 0 and "Stop (from bernstein, 18 October 2026)." in out and out.endswith("Dry run: nothing was sent.\n")
    assert sent(world) == []


def test_stop_all_with_nobody_on_duty_says_so(world):
    world.duty({"bernstein": "fresh", "recipes": "stale"})
    code, out, _err = world.conduct("stop", "--all")
    assert (code, out) == (0, "Nobody is on duty anywhere but bernstein: nothing to stop.\n")


def test_a_bad_settings_line_is_exit_2_naming_the_file(world):
    world.write_conf("PACE=fast\n")
    code, _out, err = world.conduct("stop", "--all")
    assert code == 2 and err == f"conduct: {world.conf}: line 7: unknown setting PACE\n"


def test_an_unreadable_listing_or_a_missing_lobster_mail_is_exit_4(world):
    with open(os.path.join(world.bin, "duty.json"), "w") as f:
        f.write("[")
    code, _out, err = world.conduct("stop", "--all")
    assert code == 4 and err == "conduct: lobster-mail duty status --all --json did not print the expected JSON\n"
    os.remove(os.path.join(world.bin, "lobster-mail"))
    code, _out, err = world.conduct("stop", "--all")
    assert code == 4 and err.startswith("conduct: lobster-mail duty status --all could not be run")
