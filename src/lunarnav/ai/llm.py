# ABOUTME: LLM provider port and the Claude Code CLI adapter (spec AI-4), structured JSON only
# ABOUTME: Owner: Gian. The CLI runs headless in an empty folder and sees only the task prompt

"""LLM access for the AI module.

``LlmClient`` is the substitution point (spec AI-4): the assistant depends on it only, and the
provider is chosen by ``LUNARNAV_LLM_PROVIDER``. ``ClaudeCliClient`` runs ``claude -p`` with
every source of context switched off (no settings, CLAUDE.md, skills, MCP servers or tools,
empty working directory), so the model receives only the system prompt and the request.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Protocol


class LlmError(RuntimeError):
    """The LLM could not produce a valid answer (provider failure, timeout, invalid output)."""


class LlmClient(Protocol):
    """A language model that answers with JSON matching a schema."""

    def complete_json(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Return the model's answer to ``prompt`` as a JSON object valid against ``schema``.

        Args:
            system: Task instructions (system prompt).
            prompt: The request, including any data the model needs.
            schema: JSON Schema of the expected object.

        Raises:
            LlmError: If no valid answer is obtained.
        """
        ...


def find_claude_executable() -> str | None:
    """Locate the Claude Code CLI.

    Looks at ``LUNARNAV_CLAUDE_BIN``, then ``PATH``, then the native installer's default folder
    (``~/.local/bin``), which is not always on ``PATH`` on Windows.

    Returns:
        Path of the executable, or None if not found.
    """
    configured = os.environ.get("LUNARNAV_CLAUDE_BIN")
    if configured:
        return configured
    found = shutil.which("claude")
    if found:
        return found
    for name in ("claude.exe", "claude"):
        candidate = Path.home() / ".local" / "bin" / name
        if candidate.is_file():
            return str(candidate)
    return None


def parse_cli_output(stdout: str) -> dict[str, Any]:
    """Extract the structured answer from ``claude -p --output-format json`` output.

    Args:
        stdout: Standard output of the CLI.

    Returns:
        The ``structured_output`` object.

    Raises:
        LlmError: If the output is not JSON, reports an error, or has no structured answer.
    """
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise LlmError(f"Claude CLI returned non-JSON output: {stdout[:200]!r}") from error
    if not isinstance(data, dict):
        raise LlmError("Claude CLI returned an unexpected JSON value")
    if data.get("is_error") or data.get("subtype") != "success":
        raise LlmError(f"Claude CLI error: {str(data.get('result', ''))[:300]}")
    answer = data.get("structured_output")
    if not isinstance(answer, dict):
        raise LlmError("Claude CLI answer has no structured output")
    return answer


class ClaudeCliClient:
    """``LlmClient`` backed by the Claude Code CLI in headless mode (the user's logged-in plan).

    Attributes:
        executable: Path of the ``claude`` executable.
        model: Model name passed to ``--model``; None keeps the CLI default.
        timeout_s: Maximum seconds per call.
    """

    def __init__(self, executable: str, model: str | None = None, timeout_s: float = 120.0) -> None:
        """Configure the client.

        Args:
            executable: Path of the ``claude`` executable.
            model: Optional model name.
            timeout_s: Maximum seconds per call.
        """
        self.executable = executable
        self.model = model
        self.timeout_s = timeout_s

    def command(self, system_file: Path, schema: dict[str, Any]) -> list[str]:
        """Return the CLI arguments for one call.

        Args:
            system_file: File holding the system prompt.
            schema: JSON Schema of the answer.
        """
        command = [
            self.executable,
            "-p",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(schema, separators=(",", ":")),
            "--system-prompt-file",
            str(system_file),
            "--setting-sources",
            "",
            "--disable-slash-commands",
            "--strict-mcp-config",
            "--exclude-dynamic-system-prompt-sections",
            "--tools",
            "",
        ]
        if self.model:
            command += ["--model", self.model]
        return command

    def complete_json(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Run one headless CLI call; the prompt goes through standard input.

        Raises:
            LlmError: On a timeout, a failed process or an invalid answer.
        """
        with tempfile.TemporaryDirectory(prefix="lunarnav-llm-") as folder:
            system_file = Path(folder) / "system.txt"
            system_file.write_text(system, encoding="utf-8")
            try:
                completed = subprocess.run(
                    self.command(system_file, schema),
                    input=prompt,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    cwd=folder,
                    timeout=self.timeout_s,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise LlmError(f"Claude CLI timed out after {self.timeout_s:.0f} s") from error
        if completed.returncode != 0 and not completed.stdout:
            raise LlmError(f"Claude CLI failed: {completed.stderr.strip()[:300]}")
        return parse_cli_output(completed.stdout)


def build_llm_client() -> LlmClient:
    """Build the LLM client chosen by ``LUNARNAV_LLM_PROVIDER`` (default ``cli``).

    Optional settings: ``LUNARNAV_LLM_MODEL`` (model name), ``LUNARNAV_CLAUDE_BIN`` (CLI path).

    Raises:
        RuntimeError: If the CLI is not installed.
        ValueError: If the provider is unknown or not implemented yet.
    """
    provider = os.environ.get("LUNARNAV_LLM_PROVIDER", "cli")
    if provider != "cli":
        raise ValueError(f"LLM provider {provider!r} is not implemented (use 'cli')")
    executable = find_claude_executable()
    if executable is None:
        raise RuntimeError("Claude Code CLI not found: install it or set LUNARNAV_CLAUDE_BIN")
    return ClaudeCliClient(executable, model=os.environ.get("LUNARNAV_LLM_MODEL") or None)
