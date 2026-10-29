"""Publish metadata from a reviewed bundle checkout into the platform release catalog."""
import argparse
import json
import subprocess
from pathlib import Path

from astrophotoflow.modules.software.bundles import read_bundle

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
catalog = json.loads(args.output.read_text(encoding='utf-8')) if args.output.exists() else {}
catalog[manifest.package_id] = dict(repository=args.repository, tag=args.tag, commit=commit,
                                    manifest=manifest.model_dump(), operations=operations, nodes=nodes)
args.output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
