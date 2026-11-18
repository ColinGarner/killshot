"""The `killshot` command: settings from .env, and clear messages when something's missing."""
import os

import pytest

from killshot import cli


def test_env_file_values_are_loaded_but_never_override_real_variables(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# a comment\n\nKILLSHOT_TEST_A=from-file\nKILLSHOT_TEST_B = spaced \n")
    monkeypatch.delenv("KILLSHOT_TEST_A", raising=False)
    monkeypatch.setenv("KILLSHOT_TEST_B", "from-shell")
    cli.load_env(env)
    assert os.environ["KILLSHOT_TEST_A"] == "from-file"
    assert os.environ["KILLSHOT_TEST_B"] == "from-shell"
    monkeypatch.delenv("KILLSHOT_TEST_A")


def test_a_missing_env_file_is_fine(tmp_path):
    cli.load_env(tmp_path / ".env")  # no error


def test_missing_settings_say_which_and_where_to_put_them(monkeypatch):
    monkeypatch.delenv("CBBD_API_KEY", raising=False)
    with pytest.raises(SystemExit) as stop:
        cli.require("CBBD_API_KEY")
    assert "CBBD_API_KEY" in str(stop.value) and ".env" in str(stop.value)


def test_help_lists_the_commands(capsys):
    cli.main(["--help"])
    out = capsys.readouterr().out
    assert "killshot start" in out and "killshot migrate" in out


def test_an_unknown_command_points_to_help():
    with pytest.raises(SystemExit) as stop:
        cli.main(["deploy"])
    assert "killshot --help" in str(stop.value)


def test_tools_run_as_subcommands(capsys):
    cli.main(["inspect", "tests/fixtures/cbbd_372750.json.gz"])
    assert "Kansas 89, Kentucky 69" in capsys.readouterr().out
