from pathlib import Path
import hashlib
import json
import shutil
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    vendor = ROOT / "src/astrophotoflow/vendor"
    source = ROOT / "engine/ComfyUI"
    target = vendor / "comfyui-0.42.0.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file() and not {"__pycache__", ".pytest_cache"}.intersection(path.parts):
                entry = zipfile.ZipInfo(path.relative_to(source.parent).as_posix(), (2026, 10, 25, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(entry, path.read_bytes())
    manifest_path = vendor / "comfyui-source.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["upstream_sha256"] = "95b5146939bcb4c33d17334001698beec5c88b83493beb13a8ba75a86e033967"
    manifest["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest["frontend_commit"] = "c875ee420aa027a359b2953361eb3b356b7bef00"
    manifest["runtime_version"] = "native-web-0.1.0"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(ROOT / "frontend/LICENSE", vendor / "comfyui-frontend-LICENSE")
    print(f"Native engine: {manifest['sha256']}")


if __name__ == "__main__":
    main()
