"""Tests for the CLI app (Build Queue v2.1 Tasks 106-107)."""

from __future__ import annotations

from analytics_platform.cli.app import main


class TestCli:
    def test_validate_config(self, capsys) -> None:
        rc = main(["validate-config", "--plan-id", "p1"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "plan-ok" in captured.out
        assert "p1" in captured.out

    def test_profile_run(self, capsys) -> None:
        rc = main(["profile-run", "--plan-id", "p1", "--run-id", "r1"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "run-ok" in captured.out
        assert "r1" in captured.out
