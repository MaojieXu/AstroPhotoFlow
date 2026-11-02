"""Explicit Bundle capabilities; implementations live with their owners."""
from .adapter import adapter_plan, collect_result, failure_reason, progress_reader
from .catalog import metadata, operation, operation_from_entry, release
from .git import ensure_git, remove_checkout, run_git
from .install import checkout

__all__ = ['adapter_plan', 'checkout', 'collect_result', 'ensure_git', 'failure_reason', 'metadata', 'operation', 'operation_from_entry', 'progress_reader', 'release', 'remove_checkout', 'run_git']
