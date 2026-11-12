"""Import a trusted Bundle as an isolated Python package, using current source."""

import hashlib
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from threading import RLock
from types import ModuleType


class BundleSourceLoader(importlib.machinery.SourceFileLoader):
    """Timestamp bytecode cannot detect same-size rapid helper edits."""

    def get_code(self, fullname):
        path = self.get_filename(fullname)
        return self.source_to_code(self.get_data(path), path)


class BundleFinder(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.roots: dict[str, Path] = {}

    def find_spec(self, fullname, path=None, target=None):
        namespace, _, relative = fullname.partition('.')
        root = self.roots.get(namespace)
        if root is None:
            return None
        location = root.joinpath(*relative.split('.')) if relative else root
        package = location / '__init__.py'
        source = package if package.is_file() else location.with_suffix('.py') if relative else None
        if source is not None and source.is_file():
            if not source.resolve().is_relative_to(root):
                raise ImportError('Bundle module escapes its source directory.')
            return importlib.util.spec_from_file_location(
                fullname, source, loader=BundleSourceLoader(fullname, str(source)),
                submodule_search_locations=[str(location)] if package.is_file() else None,
            )
        if location.is_dir():
            if not location.resolve().is_relative_to(root):
                raise ImportError('Bundle package escapes its source directory.')
            spec = importlib.machinery.ModuleSpec(fullname, loader=None, is_package=True)
            spec.submodule_search_locations = [str(location)]
            return spec
        # Do not fall through to timestamp bytecode or a deleted module.
        raise ModuleNotFoundError(f'Bundle module not found: {fullname}', name=fullname)


FINDER = BundleFinder()
LOCK = RLock()
FINGERPRINTS: dict[str, str] = {}


def clear_namespace(namespace: str) -> None:
    for name in list(sys.modules):
        if name == namespace or name.startswith(namespace + '.'):
            del sys.modules[name]


def load_adapter(root: Path, adapter: str, fingerprint: str) -> ModuleType:
    """Invalidate the complete Bundle namespace when its adopted content changes."""
    root = root.resolve()
    relative = Path(adapter)
    source = (root / relative).resolve()
    if (not source.is_relative_to(root) or relative.suffix != '.py'
            or not all(part.isidentifier() for part in relative.with_suffix('').parts)):
        raise ValueError('Bundle adapter must be a contained Python module.')
    namespace = 'apf_bundle_' + hashlib.sha256(str(root).encode()).hexdigest()
    with LOCK:
        if FINDER not in sys.meta_path:
            sys.meta_path.insert(0, FINDER)
        FINDER.roots[namespace] = root
        if FINGERPRINTS.get(namespace) != fingerprint:
            clear_namespace(namespace)
            importlib.invalidate_caches()
            FINGERPRINTS[namespace] = fingerprint
        try:
            return importlib.import_module(namespace + '.' + '.'.join(relative.with_suffix('').parts))
        except Exception:
            # A later explicit load may retry; never reuse a partial import tree.
            clear_namespace(namespace)
            FINGERPRINTS.pop(namespace, None)
            raise
