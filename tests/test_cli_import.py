from __future__ import annotations

from global_git.gitglobal_cli import main


def test_gitglobal_main_runs(monkeypatch, capsys):
    monkeypatch.setenv("GLOBAL_GIT_NO_ANIMATION", "1")
    exit_code = main([])
    assert exit_code == 0

    stdout, stderr = capsys.readouterr()
    assert "Active languages" in stdout
    assert stderr == ""
