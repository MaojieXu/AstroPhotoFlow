import hashlib
import json

from astrophotoflow.contracts.development import BundleDevelopmentConfig
from astrophotoflow.modules.software.metadata import contained


def digest_files(root, paths):
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes() if path.is_file() else b'missing')
    return digest.hexdigest()


def build_inputs(root):
    try:
        content = (root / 'development.json').read_bytes()
    except FileNotFoundError:
        return None, ''
    config = BundleDevelopmentConfig.model_validate_json(content)
    module = config.build
    script = contained(root, '/'.join(module.split('.')) + '.py')
    if not script.is_file():
        raise ValueError('Development build module is missing.')
    paths = {root / 'development.json', script}
    for pattern in config.watch:
        for path in root.glob(pattern):
            if path.is_file():
                contained(root, path.relative_to(root).as_posix())
                paths.add(path)
    return module, digest_files(root, paths)


def adapter_paths(root, adapter):
    entry = contained(root, adapter)
    return {entry, *(contained(root, str(path.relative_to(root)))
                    for path in entry.parent.rglob('*.py') if path.is_file())}


def content_fingerprint(root):
    paths = {root / 'bundle.json'}
    try:
        manifest = json.loads((root / 'bundle.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return digest_files(root, paths)
    for name in [*manifest['operations'], *manifest['nodes'], *manifest.get('locales', {}).values()]:
        paths.add(contained(root, name))
    paths.update(adapter_paths(root, manifest['adapter']))
    return digest_files(root, paths)
