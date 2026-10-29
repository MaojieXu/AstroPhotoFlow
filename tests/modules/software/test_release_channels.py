import pytest
from astrophotoflow.contracts.bundles import BundleManifest
from astrophotoflow.modules.software.bundles import release


@pytest.mark.parametrize('channel,version', [('dev','0.2.0-dev.1'),('stable','0.2.0')])
def test_release_channels_accept_their_own_versions(channel,version):
    manifest=dict(release('siril')['manifest'],release_channel=channel,bundle_version=version)
    assert BundleManifest.model_validate(manifest).release_channel==channel


@pytest.mark.parametrize('channel,version', [('stable','0.2.0-dev.1'),('dev','0.2.0')])
def test_development_and_production_versions_cannot_be_mislabeled(channel,version):
    with pytest.raises(ValueError):
        BundleManifest.model_validate(dict(release('siril')['manifest'],release_channel=channel,bundle_version=version))
