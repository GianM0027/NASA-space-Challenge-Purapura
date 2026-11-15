# ABOUTME: Tests for locating the Claude Code CLI executable (spec AI-4)
# ABOUTME: The npm shim without extension must never be picked on Windows

from __future__ import annotations

from pathlib import Path

import pytest

from lunarnav.ai import llm


def _fake_which(found: dict[str, str]):  # type: ignore[no-untyped-def]
    return lambda name: found.get(name)


def test_windows_prefers_runnable_shim_over_extensionless(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("LUNARNAV_CLAUDE_BIN", raising=False)
    monkeypatch.setattr(llm.Path, "home", lambda: tmp_path)
    found = {"claude": r"C:\npm\claude", "claude.cmd": r"C:\npm\claude.cmd"}
    monkeypatch.setattr(llm.shutil, "which", _fake_which(found))
    assert llm.find_claude_executable(windows=True) == r"C:\npm\claude.cmd"


def test_windows_prefers_exe_over_cmd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("LUNARNAV_CLAUDE_BIN", raising=False)
    monkeypatch.setattr(llm.Path, "home", lambda: tmp_path)
    found = {"claude.cmd": r"C:\npm\claude.cmd", "claude.exe": r"C:\bin\claude.exe"}
    monkeypatch.setattr(llm.shutil, "which", _fake_which(found))
    assert llm.find_claude_executable(windows=True) == r"C:\bin\claude.exe"


def test_posix_uses_bare_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("LUNARNAV_CLAUDE_BIN", raising=False)
    monkeypatch.setattr(llm.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(llm.shutil, "which", _fake_which({"claude": "/usr/bin/claude"}))
    assert llm.find_claude_executable(windows=False) == "/usr/bin/claude"


def test_configured_path_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUNARNAV_CLAUDE_BIN", "custom-claude")
    assert llm.find_claude_executable(windows=True) == "custom-claude"


def test_native_installer_folder_is_the_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("LUNARNAV_CLAUDE_BIN", raising=False)
    monkeypatch.setattr(llm.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(llm.shutil, "which", _fake_which({}))
    exe = tmp_path / ".local" / "bin" / "claude.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    assert llm.find_claude_executable(windows=True) == str(exe)
    exe.unlink()
    assert llm.find_claude_executable(windows=True) is None
