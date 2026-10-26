from pathlib import Path
import hashlib
import json
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    vendor = ROOT / "src/astrophotoflow/vendor"
    source = ROOT / "engine/ComfyUI"
    target = vendor / "comfyui-0.42.0.zip"
    staging = ROOT / ".artifacts/build/engine"
    staging.mkdir(parents=True, exist_ok=True)
    staged_archive = staging / target.name
    with zipfile.ZipFile(staged_archive, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file() and not {"__pycache__", ".pytest_cache"}.intersection(path.parts):
                entry = zipfile.ZipInfo(path.relative_to(source.parent).as_posix(), (2026, 10, 25, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(entry, path.read_bytes())
    manifest_path = vendor / "comfyui-source.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["upstream_sha256"] = "95b5146939bcb4c33d17334001698beec5c88b83493beb13a8ba75a86e033967"
    manifest["sha256"] = hashlib.sha256(staged_archive.read_bytes()).hexdigest()
    manifest["frontend_commit"] = "c875ee420aa027a359b2953361eb3b356b7bef00"
    manifest["runtime_version"] = "native-web-0.1.0"
    resources = {
        target: staged_archive.read_bytes(),
        manifest_path: (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
        vendor / "comfyui-frontend-LICENSE": (ROOT / "frontend/LICENSE").read_bytes(),
    }
    for destination, content in resources.items():
        if destination.is_file() and destination.read_bytes() == content:
            continue
        pending = staging / (destination.name + ".pending")
        pending.write_bytes(content)
        pending.replace(destination)
    print(f"Native engine: {manifest['sha256']}")


if __name__ == "__main__":
    main()
