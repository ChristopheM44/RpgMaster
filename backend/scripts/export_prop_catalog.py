"""Exporte le catalogue sémantique des props vers le frontend.

    cd backend && .venv/bin/python scripts/export_prop_catalog.py

Écrit ``frontend/src/engine3d/assets/propCatalog.generated.ts`` depuis
``app/engine/prop_catalog.py`` (source unique). Un test vérifie la fraîcheur.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.engine.prop_catalog import render_typescript  # noqa: E402

OUT = BACKEND.parent / "frontend" / "src" / "engine3d" / "assets" / "propCatalog.generated.ts"


def main() -> None:
    OUT.write_text(render_typescript(), encoding="utf-8")
    print(f"écrit : {OUT.relative_to(BACKEND.parent)}")


if __name__ == "__main__":
    main()
