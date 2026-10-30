import os
from pathlib import Path


def bundle_environment(executable: Path) -> dict[str, str]:
    environment = os.environ.copy()
    if os.name == "nt":
        windows = Path(os.environ["SystemRoot"])
        environment["PATH"] = os.pathsep.join(map(str, (executable.resolve().parent, windows / "System32", windows)))
    return environment
