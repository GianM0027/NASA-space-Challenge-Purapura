# ABOUTME: Writes frontend/src/api/contracts.ts: TypeScript types generated from the contracts
# ABOUTME: Owner: Gian. Rerun after any contract or API request change; a test checks the file

"""Export the contract types for the frontend.

Run with ``uv run python scripts/api_export_types.py``.
"""

from __future__ import annotations

from pathlib import Path

from lunarnav.api.typescript import render_typescript

OUT = Path(__file__).resolve().parents[1] / "frontend" / "src" / "api" / "contracts.ts"


def main() -> None:
    """Write the generated types with LF line endings."""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render_typescript(), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
