import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile


def test_engine_build_only_publishes_changed_resources(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / "scripts/build_engine.py"
    spec = importlib.util.spec_from_file_location("engine_build", path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    source = tmp_path / "engine/ComfyUI"
    vendor = tmp_path / "src/astrophotoflow/vendor"
    frontend = tmp_path / "frontend"
    source.mkdir(parents=True)
    vendor.mkdir(parents=True)
    frontend.mkdir()
    (source / "main.py").write_text("first", encoding="utf-8")
    (frontend / "LICENSE").write_text("license\n", encoding="utf-8")
    (vendor / "comfyui-source.json").write_text("{}", encoding="utf-8")
    builder.main()
    archive = vendor / "comfyui-0.42.0.zip"
    first = archive.read_bytes()
    published = []
    replace = Path.replace

    def record(path, target):
        published.append(target.name)
        return replace(path, target)

    monkeypatch.setattr(Path, "replace", record)
    (vendor / "comfyui-frontend-LICENSE").write_bytes(b"license\r\n")
    builder.main()
    assert published == []
    assert (vendor / "comfyui-frontend-LICENSE").read_bytes() == b"license\r\n"
    assert archive.read_bytes() == first
    (source / "main.py").write_text("second", encoding="utf-8")
    builder.main()
    assert set(published) == {"comfyui-0.42.0.zip", "comfyui-source.json"}
    with zipfile.ZipFile(archive) as built:
        assert built.read("ComfyUI/main.py") == b"second"
    manifest = json.loads((vendor / "comfyui-source.json").read_text(encoding="utf-8"))
    assert manifest["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
