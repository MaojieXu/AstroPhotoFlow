from pathlib import Path

import pytest


@pytest.fixture
def synthetic_bundle_catalog(monkeypatch):
    """Use authored contract fixtures rather than the product release directory."""
    path = Path(__file__).parent / 'fixtures/bundles/catalog.json'
    monkeypatch.setenv('ASTROPHOTOFLOW_BUNDLE_CATALOG', str(path))
