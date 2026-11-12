import importlib.util
import os
import subprocess
from pathlib import Path

from astrophotoflow.core.workbench import install_frontend


def directory_link(link: Path, target: Path) -> None:
    if os.name == "nt":
        subprocess.run(
            [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", "mklink", "/J", str(link), str(target)],
            check=True, capture_output=True,
        )
    else:
        link.symlink_to(target, target_is_directory=True)


def test_replacing_legacy_links_keeps_the_shared_snapshot(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/build_frontend.py"
    spec = importlib.util.spec_from_file_location("build_frontend", script)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)

    snapshot = tmp_path / "old-snapshot"
    snapshot.mkdir()
    (snapshot / "index.html").write_text("old", encoding="utf-8")
    assets = tmp_path / ".artifacts/build/frontend"
    assets.parent.mkdir(parents=True)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    web = workspace / "web"
    directory_link(assets, snapshot)
    directory_link(web, snapshot)

    builder.prepare_output(assets)
    assert not assets.exists()
    assert (web / "index.html").read_text(encoding="utf-8") == "old"
    assets.mkdir()
    (assets / "index.html").write_text("new", encoding="utf-8")
    assert install_frontend(workspace, assets) == web
    assert not web.is_junction() and not web.is_symlink()
    assert (web / "index.html").read_text(encoding="utf-8") == "new"
    assert (snapshot / "index.html").read_text(encoding="utf-8") == "old"
