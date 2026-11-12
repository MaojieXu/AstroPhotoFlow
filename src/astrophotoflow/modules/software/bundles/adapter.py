from pathlib import Path

from astrophotoflow.contracts.bundles import (
    BundleCollectedResult,
    BundleFile,
    BundleManifest,
    BundleProgress,
    NamedProcessPlan,
)
from astrophotoflow.modules.software import development
from astrophotoflow.modules.software.metadata import contained

from .catalog import metadata
from .loader import load_adapter


def _adapter(workspace, package_id, root, manifest):
    commit = development.identity(workspace, package_id)['commit'] or ''
    return load_adapter(root, manifest.adapter, commit + ':' + development.content_fingerprint(root))


def adapter_plan(workspace: Path, package_id: str, operation_id: str, sources, parameters, directory, **options):
    root = development.source_root(workspace, package_id)
    manifest, _, _ = metadata(workspace, package_id)
    adapter = _adapter(workspace, package_id, root, manifest)
    plan = NamedProcessPlan.model_validate(adapter.build_plan(operation_id, sources, parameters, directory, **options))
    paths = [plan.temporary_directory]
    for output in plan.outputs.values():
        paths.extend(file.path for file in output.files)
        for pattern in output.patterns + output.supporting_patterns:
            if Path(pattern.pattern).is_absolute() or '..' in Path(pattern.pattern).parts:
                raise ValueError('Bundle output pattern escapes the invocation directory.')
            contained(directory, pattern.pattern)
    for output in [*paths, *([plan.linear_sample] if plan.linear_sample else [])]:
        if not output.resolve().is_relative_to(directory.resolve()):
            raise ValueError('Bundle output escapes the invocation directory.')
    return plan


def collect_result(workspace: Path, package_id: str, operation_id: str, plan, directory: Path, log_path: Path):
    root = development.source_root(workspace, package_id)
    manifest, _, _ = metadata(workspace, package_id)
    adapter = _adapter(workspace, package_id, root, manifest)
    adapter.parse_result(operation_id, directory, plan, log_path)
    outputs, supporting = {}, {}

    def matches(pattern):
        paths = sorted(directory.glob(pattern.pattern))
        if len(paths) < pattern.minimum_count:
            raise ValueError('Bundle did not produce the required output: ' + pattern.pattern)
        return [BundleFile(path=path, format=pattern.format, allow_empty=pattern.allow_empty, frame_count=pattern.frame_count) for path in paths]

    for name, output in plan.outputs.items():
        outputs[name] = list(output.files)
        for pattern in output.patterns:
            outputs[name].extend(matches(pattern))
        supporting[name] = [file for pattern in output.supporting_patterns for file in matches(pattern)]
    result = BundleCollectedResult(outputs=outputs, supporting_outputs=supporting)
    for group in [*result.outputs.values(), *result.supporting_outputs.values()]:
        for file in group:
            contained(directory, str(file.path))
            if file.allow_empty and file.format != 'other':
                raise ValueError('Only declared non-scientific file outputs may be empty.')
            if not file.path.is_file() or (file.path.stat().st_size == 0 and not file.allow_empty):
                raise ValueError('Bundle output is missing or empty: ' + str(file.path))
    return result


def progress_reader(workspace: Path, package_id: str):
    root = development.source_root(workspace, package_id)
    manifest = BundleManifest.model_validate_json((root / 'bundle.json').read_text(encoding='utf-8'))
    adapter = _adapter(workspace, package_id, root, manifest)
    return lambda text: BundleProgress.model_validate(adapter.parse_progress(text))


def failure_reason(workspace: Path, package_id: str, log_path: Path):
    root = development.source_root(workspace, package_id)
    manifest, _, _ = metadata(workspace, package_id)
    adapter = _adapter(workspace, package_id, root, manifest)
    return str(adapter.parse_failure(log_path))
