"""Watch only Bundle controls, declarations, authored inputs and source identity."""

import json
from pathlib import Path

from astrophotoflow.contracts.development import BundleDevelopmentConfig, BundleWatchPath
from astrophotoflow.modules.software.metadata import catalog, contained

from .bindings import REPOSITORY_BINDINGS, bindings_path, read_bindings, receipt_path, repository_roots, resolve_bindings


def git_watch_paths(root: Path) -> list[BundleWatchPath]:
    directory = root / '.git'
    if directory.is_file():
        value = directory.read_text(encoding='utf-8').strip()
        if not value.startswith('gitdir: '):
            raise ValueError('Invalid Bundle Git directory reference.')
        directory = (root / value.removeprefix('gitdir: ')).resolve()
    result = [BundleWatchPath(root / '.git'), BundleWatchPath(directory / 'HEAD'),
              BundleWatchPath(directory / 'index')]
    common = directory
    if (directory / 'commondir').is_file():
        result.append(BundleWatchPath(directory / 'commondir'))
        common = (directory / (directory / 'commondir').read_text().strip()).resolve()
    result.append(BundleWatchPath(common / 'packed-refs'))
    if (directory / 'HEAD').is_file():
        head = (directory / 'HEAD').read_text().strip()
        if head.startswith('ref: '):
            result.append(BundleWatchPath(contained(common, head.removeprefix('ref: '))))
    return result


def bundle_watch_paths(workspace: Path) -> set[BundleWatchPath]:
    interests = {BundleWatchPath(bindings_path(workspace)),
                 BundleWatchPath(workspace / 'software', directory=True)}
    values = read_bindings(workspace)
    repository = values.get(REPOSITORY_BINDINGS)
    if repository is not None:
        directory = Path(repository['root'])
        # Keep Windows watch handles on the parent so a checkout can be moved.
        interests.add(BundleWatchPath(directory, directory=True, watch_subtree=True))
        interests.update(BundleWatchPath(root / 'bundle.json') for root in repository_roots(directory))
    sources = resolve_bindings(values)
    for package_id in set(catalog()) | sources.keys():
        parent = workspace / 'software' / package_id
        root = Path(sources[package_id]['root']) if package_id in sources else parent / 'bundle'
        interests.update({BundleWatchPath(parent, directory=True), BundleWatchPath(root, directory=True),
                          BundleWatchPath(root / 'bundle.json'), BundleWatchPath(parent / 'state.json'),
                          BundleWatchPath(parent / 'bundle-lock.json'), BundleWatchPath(receipt_path(workspace, package_id))})
        try:
            manifest = json.loads((root / 'bundle.json').read_text(encoding='utf-8'))
            for value in [*manifest['operations'], *manifest['nodes'], *manifest.get('locales', {}).values()]:
                interests.add(BundleWatchPath(contained(root, value)))
            interests.add(BundleWatchPath(contained(root, manifest['adapter']).parent, directory=True, recursive=True))
        except (OSError, KeyError, TypeError, ValueError):
            # The manifest control stays observed so a repair can be adopted.
            pass
        if package_id not in sources:
            continue
        interests.add(BundleWatchPath(root / 'development.json'))
        try:
            interests.update(git_watch_paths(root))
        except (OSError, ValueError):
            interests.add(BundleWatchPath(root / '.git'))
        try:
            config = BundleDevelopmentConfig.model_validate_json((root / 'development.json').read_bytes())
            for pattern in config.watch:
                parts = Path(pattern).parts
                wildcard = next((i for i, part in enumerate(parts) if any(c in part for c in '*?[')), None)
                if wildcard is None:
                    interests.add(BundleWatchPath(contained(root, pattern)))
                else:
                    prefix = contained(root, Path(*parts[:wildcard]).as_posix())
                    interests.add(BundleWatchPath(prefix, directory=True, recursive=len(parts[wildcard:]) > 1))
            interests.add(BundleWatchPath(contained(root, config.build.replace('.', '/') + '.py')))
        except (OSError, KeyError, TypeError, ValueError):
            # Refreshing the source publishes the real generation error.
            pass
    return interests
