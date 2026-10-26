from importlib.resources import files
import subprocess
import sys


def test_backend_migrations_are_package_resources():
    backend = files("astrophotoflow.core.database")
    assert backend.joinpath("alembic.ini").is_file()
    migrations = sorted(path.name for path in backend.joinpath("alembic/versions").iterdir() if path.suffix == ".py")
    assert migrations == [
        "0001_foundation.py", "0002_asset_ingestion.py", "0003_capture_profile_gain_mode.py",
        "0004_library_entry_removal_and_asset_facts.py", "0005_dataset_removal_version_snapshot.py",
        "0006_library_trash_cleanup_state.py", "0007_setups_and_calibration.py",
        "0008_asset_equipment_snapshot.py", "0009_remove_legacy_capture_profiles.py",
    ]


def test_comfyui_package_import_does_not_register_extension():
    subprocess.run(
        [sys.executable, "-c", "import sys; import astrophotoflow.comfyui; assert 'server' not in sys.modules"],
        check=True,
        timeout=10,
    )
