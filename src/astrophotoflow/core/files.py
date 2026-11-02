"""Small filesystem primitives shared by concrete state owners."""

import os
import time
from pathlib import Path


def replace_file(source: Path, destination: Path) -> None:
    """Commit prepared bytes; retry only observed Windows reader/access races."""
    for attempt in range(5):
        try:
            os.replace(source, destination)
            return
        except PermissionError as exc:
            if os.name != 'nt' or getattr(exc, 'winerror', None) != 5 or attempt == 4:
                raise
            time.sleep(0.05)
