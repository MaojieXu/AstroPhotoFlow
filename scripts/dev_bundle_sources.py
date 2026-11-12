"""Read or configure Bundle sources using the prepared development interpreter."""
import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--bundle-source', action='append', default=[])
    parser.add_argument('--clear-bundle-source', action='append', default=[])
    repository = parser.add_mutually_exclusive_group()
    repository.add_argument('--repo-bundles', action='store_true', help='Watch the checkout’s bundles/ directory in this workspace.')
    repository.add_argument('--clear-repo-bundles', action='store_true', help='Stop discovering Bundle checkouts for this workspace.')
    args = parser.parse_args()

    from astrophotoflow.modules.software import development

    if args.repo_bundles or args.clear_repo_bundles:
        directory = Path(__file__).resolve().parents[1] / 'bundles' if args.repo_bundles else None
        sources = development.configure(args.workspace, args.bundle_source, args.clear_bundle_source, sys.executable,
                                        repository=directory, clear_repository=args.clear_repo_bundles)
    elif args.bundle_source or args.clear_bundle_source:
        sources = development.configure(args.workspace, args.bundle_source, args.clear_bundle_source, sys.executable)
    else:
        sources = {key: development.source_state(args.workspace, key).model_dump(mode='json')
                   for key in development.bindings(args.workspace)}
    print(json.dumps(sources, ensure_ascii=False))


if __name__ == '__main__':
    main()
