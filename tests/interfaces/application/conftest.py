import pytest


@pytest.fixture(autouse=True)
def application_bundle_catalog(synthetic_bundle_catalog):
    """Application unit tests exercise the host protocol with synthetic metadata."""
