"""Publish metadata from a reviewed bundle checkout into the platform release catalog."""
import argparse
import json
import subprocess
from pathlib import Path

from astrophotoflow.modules.software.bundles import contained, read_bundle
from astrophotoflow.modules.software.metadata import read_bundle_locales

parser = argparse.ArgumentParser()
parser.add_argument('checkout', type=Path)
parser.add_argument('--repository', required=True)
parser.add_argument('--tag', required=True)
parser.add_argument('--output', type=Path, default=Path('src/astrophotoflow/vendor/bundle-catalog.json'))
args = parser.parse_args()
manifest, operations, nodes = read_bundle(args.checkout)
if args.tag != 'v' + manifest.bundle_version:
    raise SystemExit('Release tag must exactly match the bundle version and its channel.')
commit = subprocess.check_output(['git', '-c', 'safe.directory=' + args.checkout.resolve().as_posix(),
                                 '-C', str(args.checkout), 'rev-parse', args.tag + '^{commit}'], text=True).strip()
git_prefix = ['git', '-c', 'safe.directory=' + args.checkout.resolve().as_posix(), '-C', str(args.checkout)]
if subprocess.check_output([*git_prefix, 'status', '--porcelain'], text=True).strip():
    raise SystemExit('Export requires a clean, committed Bundle checkout; uncommitted files cannot be attributed to a tag.')
if subprocess.check_output([*git_prefix, 'rev-parse', 'HEAD'], text=True).strip() != commit:
    raise SystemExit('Export requires the checkout HEAD to equal the requested tag commit.')
catalog = json.loads(args.output.read_text(encoding='utf-8')) if args.output.exists() else {}
catalog[manifest.package_id] = dict(repository=args.repository, tag=args.tag, commit=commit,
                                    manifest=manifest.model_dump(), operations=operations, nodes=nodes,
                                    localizations=read_bundle_locales(args.checkout, manifest, operations),
                                    reference_files={name: contained(args.checkout, name).read_bytes().decode('utf-8')
                                                     for name in [manifest.commands, manifest.assessments] if name is not None})
args.output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
