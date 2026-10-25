from importlib.resources import files
import subprocess
import sys


def test_backend_migrations_are_package_resources():
    backend = files("astrophotoflow.backend")
    assert backend.joinpath("alembic.ini").is_file()
    migrations = sorted(path.name for path in backend.joinpath("alembic/versions").iterdir() if path.suffix == ".py")
    assert len(migrations) == 6
    assert migrations[-1] == "0006_library_trash_cleanup_state.py"


def test_comfyui_package_import_does_not_register_extension():
    subprocess.run(
        [sys.executable, "-c", "import sys; import astrophotoflow.comfyui; assert 'server' not in sys.modules"],
        check=True,
        timeout=10,
    )
