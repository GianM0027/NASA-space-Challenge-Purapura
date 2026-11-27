# ABOUTME: LLM provider port with Claude Code CLI, Anthropic API and no-LLM adapters (spec AI-4)
# ABOUTME: Owner: Gian. Structured JSON only; a user's own API key overrides the server provider

"""LLM access for the AI module.

``LlmClient`` is the substitution point (spec AI-4): the assistant depends on it only, and the
server's provider is chosen by ``LUNARNAV_LLM_PROVIDER``. ``ClaudeCliClient`` runs ``claude -p``
with every source of context switched off (no settings, CLAUDE.md, skills, MCP servers or tools,
empty working directory), so the model receives only the system prompt and the request.
``AnthropicApiClient`` calls the Messages API with structured outputs, with the server's key or
with a key a user sends for their own requests (``api_client_for_key``, decision D43).
``UnavailableLlmClient`` is the server without an LLM: AI calls fail with
``LlmUnavailableError`` and every caller falls back to its deterministic output.
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


class LlmUnavailableError(LlmError):
    """No LLM is configured: the server has none and the request carries no API key."""


class LlmAuthError(LlmError):
    """The provider rejected the API key (invalid, revoked or without permission)."""


# Default model of the Anthropic API adapter (owner's choice: the AI tasks are short extractions
# and comments, Haiku is enough and cheapest); LUNARNAV_LLM_MODEL or the visitor's pick wins.
DEFAULT_API_MODEL = "claude-haiku-5-5"
# Models a visitor may pick for their own key, by token use (cost): low, medium, high.
USER_MODELS = ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5")
# Models that accept the server-side refusal fallback (Claude Haiku 5.5 has none).
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}
# Longest accepted API key: real keys are about 110 characters; anything far longer is not a key.
MAX_API_KEY_LENGTH = 256


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


def find_claude_executable(windows: bool | None = None) -> str | None:
    """Locate the Claude Code CLI.

    Looks at ``LUNARNAV_CLAUDE_BIN``, then ``PATH``, then the native installer's default folder
    (``~/.local/bin``), which is not always on ``PATH`` on Windows. On Windows the npm install
    puts an extensionless shell script ``claude`` next to ``claude.cmd``; ``subprocess`` cannot
    run the former, so ``claude.exe`` and ``claude.cmd`` are looked up first.

    Args:
        windows: Whether to apply the Windows lookup order; None detects it from ``os.name``.

    Returns:
        Path of the executable, or None if not found.
    """
    configured = os.environ.get("LUNARNAV_CLAUDE_BIN")
    if configured:
        return configured
    if windows is None:
        windows = os.name == "nt"
    names = ("claude.exe", "claude.cmd") if windows else ("claude",)
    for name in names:
        found = shutil.which(name)
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

    provider = "cli"

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


def parse_api_message(message: Any) -> dict[str, Any]:
    """Extract the JSON answer from a Messages API response with a JSON-schema output format.

    Args:
        message: The response of ``messages.create`` (SDK object).

    Returns:
        The answer object.

    Raises:
        LlmError: If the model refused, was cut off, or returned no JSON object.
    """
    if message.stop_reason == "refusal":
        raise LlmError("the model declined to answer this request")
    if message.stop_reason == "max_tokens":
        raise LlmError("the model's answer was cut off (max_tokens)")
    text = next((block.text for block in message.content if block.type == "text"), None)
    if text is None:
        raise LlmError("the model's answer has no text")
    try:
        answer = json.loads(text)
    except json.JSONDecodeError as error:
        raise LlmError(f"the model returned non-JSON output: {text[:200]!r}") from error
    if not isinstance(answer, dict):
        raise LlmError("the model returned an unexpected JSON value")
    return answer


# Keywords that belong to one JSON type when a nullable type list is split into anyOf branches.
_TYPE_KEYWORDS = {
    "string": {"enum", "format", "pattern", "minLength", "maxLength"},
    "number": {"enum", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"},
    "integer": {"enum", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"},
    "array": {"items", "minItems", "maxItems"},
    "object": {"properties", "required", "additionalProperties"},
}


def api_json_schema(schema: Any) -> Any:
    """Rewrite a JSON Schema into the form the Messages API's structured outputs accept.

    The API rejects a type list such as ``{"type": ["string", "null"], "enum": [..., None]}``
    (every enum value must match one declared type). Each type list becomes ``anyOf`` with one
    branch per type: the keywords of that type (an enum without ``None``) and ``{"type": "null"}``.
    Everything else is copied unchanged; the Claude CLI keeps receiving the original schema.
    """
    if isinstance(schema, list):
        return [api_json_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    node = {key: api_json_schema(value) for key, value in schema.items()}
    types = node.get("type")
    if not isinstance(types, list):
        return node
    shared = {k: v for k, v in node.items() if k in {"description", "title"}}
    branches: list[dict[str, Any]] = []
    for kind in types:
        branch: dict[str, Any] = {"type": kind}
        for key in _TYPE_KEYWORDS.get(kind, set()):
            if key in node:
                branch[key] = node[key]
        if "enum" in branch:
            branch["enum"] = [value for value in branch["enum"] if value is not None]
        branches.append(branch)
    return {**shared, "anyOf": branches}


class AnthropicApiClient:
    """``LlmClient`` backed by the Anthropic Messages API with structured outputs.

    The key is used for the calls of this client only: it is never logged or stored. Errors
    carry the provider's message, which never contains the key.

    Attributes:
        model: Model id sent with every call.
        timeout_s: Maximum seconds per HTTP request.
    """

    provider = "api"

    def __init__(self, api_key: str, model: str | None = None, timeout_s: float = 60.0) -> None:
        """Create the SDK client.

        Args:
            api_key: Anthropic API key.
            model: Model id; None uses ``DEFAULT_API_MODEL``.
            timeout_s: Maximum seconds per HTTP request.

        Raises:
            RuntimeError: If the ``anthropic`` package is not installed (``uv sync --group ai``).
        """
        try:
            import anthropic
        except ImportError as error:
            raise RuntimeError("the anthropic package is missing: uv sync --group ai") from error
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key, max_retries=1, timeout=timeout_s)
        self.model = model or DEFAULT_API_MODEL
        self.timeout_s = timeout_s

    def __repr__(self) -> str:
        """Describe the client without the key."""
        return f"AnthropicApiClient(model={self.model!r})"

    def complete_json(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Run one Messages API call constrained to ``schema``.

        Effort ``low``: the tasks are short extractions and comments, and the user waits.
        Server-side refusal fallback is on, so a declined request is retried on another model.

        Raises:
            LlmAuthError: If the key is rejected.
            LlmError: On any other provider failure or an invalid answer.
        """
        anthropic = self._anthropic
        fallback: dict[str, Any] = (
            {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
            if self.model in FALLBACK_MODELS
            else {}
        )
        try:
            message = self._client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": api_json_schema(schema)},
                },
                **fallback,
            )
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as error:
            raise LlmAuthError(f"Anthropic rejected the API key: {error.message}") from error
        except anthropic.RateLimitError as error:
            raise LlmError("Anthropic rate limit reached for this API key") from error
        except anthropic.APIStatusError as error:
            raise LlmError(f"Anthropic API error {error.status_code}: {error.message}") from error
        except anthropic.APIConnectionError as error:  # includes timeouts
            raise LlmError(f"Anthropic API unreachable: {type(error).__name__}") from error
        return parse_api_message(message)


class UnavailableLlmClient:
    """``LlmClient`` used when the server has no LLM: every call asks for an API key."""

    provider = "none"

    def complete_json(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Always fail with ``LlmUnavailableError``."""
        raise LlmUnavailableError("the AI needs an Anthropic API key")


def validate_api_key(api_key: str) -> str:
    """Return the key without surrounding spaces, or raise ``ValueError`` if it cannot be one.

    Only the shape is checked (printable ASCII, no spaces, bounded length); Anthropic decides
    whether the key is valid.
    """
    key = api_key.strip()
    if not key or len(key) > MAX_API_KEY_LENGTH or not all("!" <= c <= "~" for c in key):
        raise ValueError("the API key is not a valid key string")
    return key


def api_client_for_key(api_key: str, model: str | None = None) -> AnthropicApiClient:
    """Build the API client for a key supplied by a user.

    Args:
        api_key: The visitor's Anthropic API key.
        model: One of ``USER_MODELS`` chosen by the visitor; None uses ``LUNARNAV_LLM_MODEL`` or
            ``DEFAULT_API_MODEL``.

    Raises:
        ValueError: If the key has an impossible shape or the model is not offered.
        RuntimeError: If the ``anthropic`` package is not installed.
    """
    chosen = (model or "").strip() or None
    if chosen is not None and chosen not in USER_MODELS:
        raise ValueError(f"model must be one of {', '.join(USER_MODELS)}")
    return AnthropicApiClient(
        validate_api_key(api_key), model=chosen or os.environ.get("LUNARNAV_LLM_MODEL") or None
    )


def build_llm_client() -> LlmClient:
    """Build the server's LLM client chosen by ``LUNARNAV_LLM_PROVIDER`` (default ``cli``).

    Providers: ``cli`` (Claude Code CLI with the logged-in plan), ``api`` (Anthropic API with
    the server's ``ANTHROPIC_API_KEY``), ``none`` (no server LLM: only users who send their own
    key get AI answers). Optional settings: ``LUNARNAV_LLM_MODEL`` (model name),
    ``LUNARNAV_CLAUDE_BIN`` (CLI path).

    Raises:
        RuntimeError: If the chosen provider is not available (CLI or key missing).
        ValueError: If the provider is unknown.
    """
    provider = os.environ.get("LUNARNAV_LLM_PROVIDER", "cli")
    model = os.environ.get("LUNARNAV_LLM_MODEL") or None
    if provider == "none":
        return UnavailableLlmClient()
    if provider == "api":
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key.strip():
            raise RuntimeError("LUNARNAV_LLM_PROVIDER=api needs ANTHROPIC_API_KEY")
        return AnthropicApiClient(validate_api_key(key), model=model)
    if provider != "cli":
        raise ValueError(f"unknown LLM provider {provider!r} (use 'cli', 'api' or 'none')")
    executable = find_claude_executable()
    if executable is None:
        raise RuntimeError("Claude Code CLI not found: install it or set LUNARNAV_CLAUDE_BIN")
    return ClaudeCliClient(executable, model=model)
