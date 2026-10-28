"""Export the service contract without starting a server or changing a database."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.core.config import Settings


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    temporary = root / ".artifacts" / "tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=temporary) as directory:
        settings = Settings("127.0.0.1", 8190, Path(directory), ("http://127.0.0.1:8188",), workspace=Path(directory))
        app = create_app(settings, "contract-export")
        try:
            document = app.openapi()
        finally:
            app.state.database.close()
    (root / "docs" / "api" / "openapi.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
