import hashlib

import numpy as np
import pytest
from astropy.io import fits
from PIL import Image

from astrophotoflow.core.config import Settings
from astrophotoflow.modules.data.public import check_output, render_output_preview
from astrophotoflow.modules.data.siril_preview import fits_sample, direct_fits_image


@pytest.mark.parametrize("dtype", [np.float32, np.uint16])
def test_direct_preview_preserves_output_brightness_without_auto_stretch(tmp_path, dtype):
    path = tmp_path / "output.fit"
    value = 0.5 if dtype is np.float32 else 32768
    fits.writeto(path, np.full((31, 43), value, dtype=dtype))
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    image = np.asarray(direct_fits_image(path, 0, 1024))
    assert image.shape == (31, 43, 3)
    assert np.max(np.abs(image.astype(int) - 127)) <= 1
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_linear_sample_retains_rgb_channels_and_odd_dimensions(tmp_path):
    path = tmp_path / "rgb.fit"
    data = np.arange(3 * 33 * 51, dtype=np.float32).reshape(3, 33, 51) / 6000
    fits.writeto(path, data, fits.Header({"CTYPE3": "RGB"}))
    sample = fits_sample(path, 0, 17)
    np.testing.assert_array_equal(sample, np.moveaxis(data[:, ::3, ::3], 0, -1))
    assert max(sample.shape[:2]) <= 17


def test_formal_siril_result_uses_direct_output_values(tmp_path, monkeypatch):
    from astrophotoflow.modules.data import fits_preview

    path = tmp_path / "output.fit"
    fits.writeto(path, np.full((15, 17), 0.3, dtype=np.float32))
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    checked = check_output(settings, run_directory=tmp_path, path=path, expected_format="fits")

    def forbidden(*_args, **_kwargs):
        pytest.fail("A processed Siril result must not be automatically stretched again")

    monkeypatch.setattr(fits_preview, "calculate_stretch", forbidden)
    target = tmp_path / "preview.jpg"
    render_output_preview(checked, target, max_edge=1024, auto_stretch=False)
    assert abs(float(np.asarray(Image.open(target)).mean()) - 76) <= 2


def test_siril_planar_rgb_without_ctype3_is_displayed_without_changing_file(tmp_path):
    path = tmp_path / "siril-result.fit"
    data = np.zeros((3, 17, 29), dtype=np.float32)
    data[0], data[1], data[2] = 0.2, 0.5, 0.8
    fits.writeto(path, data)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    image = np.asarray(direct_fits_image(path, 0, 1024))
    assert image.shape == (17, 29, 3)
    np.testing.assert_allclose(image[0, 0], [51, 127, 204], atol=1)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert "CTYPE3" not in fits.getheader(path)
