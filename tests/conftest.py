import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pytest

REAL_DATA_REPORTS = pytest.StashKey[list[dict]]()


def pytest_addoption(parser):
    group = parser.getgroup('real-data')
    group.addoption('--real-data-root', type=Path, default=None, help='Read-only root containing the five authored astronomy source folders.')
    group.addoption('--run-full-import', action='store_true', default=False, help='Allow the separate 514-file managed-copy test.')


def pytest_configure(config):
    config.addinivalue_line('markers', 'real_data: uses the explicitly supplied read-only astronomy corpus')
    config.addinivalue_line('markers', 'full_import: copies all 514 originals and requires --run-full-import')
    config.addinivalue_line('markers', 'plan_a: readable library layout and current calibration-state acceptance')
    config.stash[REAL_DATA_REPORTS] = []


def pytest_collection_modifyitems(config, items):
    root = Path(__file__).parent / 'real_data'
    for item in items:
        if item.path.is_relative_to(root):
            item.add_marker(pytest.mark.real_data)
            if item.path.name != 'test_catalog.py':
                item.add_marker(pytest.mark.plan_a)
        if item.get_closest_marker('full_import') and not config.getoption('--run-full-import'):
            item.add_marker(pytest.mark.skip(reason='Full managed copying requires --run-full-import.'))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if item.get_closest_marker('real_data') and (report.when == 'call' or report.failed or report.skipped):
        item.config.stash[REAL_DATA_REPORTS].append({
            'test': report.nodeid, 'phase': report.when, 'outcome': report.outcome,
            'duration_seconds': report.duration, 'details': dict(item.user_properties),
            'error': report.longreprtext if report.failed or report.skipped else None,
        })


def pytest_sessionfinish(session, exitstatus):
    reports = session.config.stash[REAL_DATA_REPORTS]
    if not reports:
        return
    priorities = {'passed': 0, 'skipped': 1, 'failed': 2}
    results = {}
    for report in reports:
        previous = results.get(report['test'], 'passed')
        results[report['test']] = max(previous, report['outcome'], key=priorities.__getitem__)
    destination = Path(__file__).resolve().parents[1] / '.artifacts/reports/real-data'
    destination.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')
    root = session.config.getoption('--real-data-root')
    (destination / f'pytest-{timestamp}.json').write_text(json.dumps({
        'source_root': str(root) if root else None, 'exit_status': int(exitstatus),
        'counts': {state: Counter(results.values())[state] for state in priorities}, 'reports': reports,
    }, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')


@pytest.fixture
def synthetic_bundle_catalog(monkeypatch):
    """Use authored contract fixtures rather than the product release directory."""
    path = Path(__file__).parent / 'fixtures/bundles/catalog.json'
    monkeypatch.setenv('ASTROPHOTOFLOW_BUNDLE_CATALOG', str(path))
