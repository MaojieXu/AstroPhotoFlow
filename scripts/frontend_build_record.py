"""Record and verify the inputs and output of a local frontend build."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / '.artifacts/build/frontend'
RECORD = ASSETS / 'build-record.json'
ENV_KEYS = ('DISTRIBUTION', 'NODE_ENV', 'ENABLE_MINIFY', 'ANALYZE_BUNDLE',
            'DISABLE_TEMPLATES_PROXY', 'GENERATE_SOURCEMAP', 'COLLECT_COVERAGE',
            'IS_NIGHTLY', 'FRONTEND_COMMIT_HASH', 'ASSET_CACHE_BUST',
            'DISABLE_VUE_PLUGINS', 'SENTRY_DSN', 'ALGOLIA_APP_ID', 'ALGOLIA_API_KEY',
            'USE_PROD_CONFIG')


def digest_files(root: Path, paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        relative = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        if path.name == 'frontend_build_record.py':
            data = data.replace(b'\r\n', b'\n')
        digest.update(len(relative).to_bytes(8, 'big'))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, 'big'))
        digest.update(data)
    return digest.hexdigest()


def inputs(root: Path, node: str, pnpm: str, env: dict[str, str]) -> dict:
    names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others',
                                     '--exclude-standard', '--', 'frontend', 'package.json',
                                     'pyproject.toml', 'scripts/build_engine.py',
                                     'scripts/frontend_build_record.py'], cwd=root).decode().split('\0')
    paths = {root / name for name in names if name and (root / name).is_file()
             and not name.startswith('frontend/docs/')
             and not (name.startswith('frontend/') and Path(name).name in {'README.md', 'AGENTS.md'})}
    for directory in (root, root / 'frontend'):
        paths.update(path for path in directory.glob('.env*') if path.is_file())
    relevant = {key: value for key, value in env.items()
                if key in ENV_KEYS or key.startswith(('VITE_', 'SENTRY_', 'COMFY_'))}
    relevant.setdefault('DISTRIBUTION', 'localhost')
    relevant = {key: hashlib.sha256(value.encode()).hexdigest() for key, value in relevant.items()}
    return {'files': digest_files(root, list(paths)), 'node': node, 'pnpm': pnpm,
            'platform': sys.platform, 'environment': relevant}


def output_digest(assets: Path) -> str:
    return digest_files(assets, [p for p in assets.rglob('*') if p.is_file() and p.name != 'build-record.json'])


def matches(assets: Path, root: Path, head: str, node: str, pnpm: str, env: dict[str, str]) -> bool:
    try:
        record = json.loads((assets / 'build-record.json').read_text(encoding='utf-8'))
        manifest = json.loads((assets / 'build-manifest.json').read_text(encoding='utf-8'))
        return ((assets / 'index.html').is_file() and manifest == {'commit': head, 'distribution': 'localhost'}
                and record['inputs'] == inputs(root, node, pnpm, env)
                and record['output'] == output_digest(assets))
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
        return False


def main() -> int:
    env = dict(os.environ)
    node = subprocess.check_output(['node', '--version'], text=True).strip()
    pnpm = subprocess.check_output(['pnpm', '--version'], text=True, shell=sys.platform == 'win32').strip()
    before = inputs(ROOT, node, pnpm, env)
    RECORD.unlink(missing_ok=True)
    commands = [[sys.executable, 'scripts/build_engine.py'], ['pnpm', 'typecheck'],
                ['pnpm', '--dir', 'frontend', 'build']]
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, check=False, shell=sys.platform == 'win32' and command[0] == 'pnpm')
        if result.returncode:
            return result.returncode
    if before != inputs(ROOT, node, pnpm, env):
        raise RuntimeError('Frontend build inputs changed during build; no reusable record written')
    RECORD.write_text(json.dumps({'inputs': before, 'output': output_digest(ASSETS)}, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
