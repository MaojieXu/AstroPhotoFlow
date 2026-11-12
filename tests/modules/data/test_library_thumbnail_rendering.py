from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from astrophotoflow.modules.data.formats import thumbnails


def _fits(path: Path, pixels: np.ndarray, *, rgb: bool = False) -> bytes:
    hdu = fits.PrimaryHDU(pixels)
    if rgb:
        hdu.header["CTYPE3"] = "RGB"
    hdu.writeto(path)
    return path.read_bytes()


def test_first_image_stretch_is_reused_for_group_without_touching_originals(tmp_path, monkeypatch):
    first = tmp_path / "first.fits"
    second = tmp_path / "second.fits"
    rng = np.random.default_rng(81)
    originals = [_fits(first, rng.normal(100, 5, (320, 480)).astype(np.float32)),
                 _fits(second, rng.normal(150, 8, (320, 480)).astype(np.float32))]
    calls = []
    calculate = thumbnails.calculate_stretch

    def counted(pixels):
        calls.append(1)
        return calculate(pixels)

    monkeypatch.setattr(thumbnails, "calculate_stretch", counted)
    first_image, recipe = thumbnails.render_thumbnail(first, "fits", 0, "mono", {})
    second_image, reused = thumbnails.render_thumbnail(second, "fits", 0, "mono", {}, recipe=recipe)

    assert len(calls) == 1
    assert reused == recipe
    assert max(first_image.size) <= 100 and max(second_image.size) <= 100
    assert first.read_bytes() == originals[0]
    assert second.read_bytes() == originals[1]


def test_incompatible_group_layout_does_not_apply_reference_recipe(tmp_path):
    mono, rgb = tmp_path / "mono.fits", tmp_path / "rgb.fits"
    _fits(mono, np.arange(1200, dtype=np.float32).reshape(30, 40))
    _fits(rgb, np.ones((3, 30, 40), dtype=np.float32), rgb=True)
    _, recipe = thumbnails.render_thumbnail(mono, "fits", 0, "mono", {})

    with pytest.raises(ValueError, match="incompatible"):
        thumbnails.render_thumbnail(rgb, "fits", 0, "rgb", {}, recipe=recipe)


@pytest.mark.parametrize("name", ["light", "bias", "dark", "flat", "dark_flat"])
def test_standalone_fits_uses_its_own_auto_stretch(tmp_path, name):
    path = tmp_path / f"master_{name}.fits"
    _fits(path, np.arange(60000, dtype=np.float32).reshape(200, 300))
    image, recipe = thumbnails.render_thumbnail(path, "fits", 0, "mono", {})
    assert max(image.size) == 100
    assert recipe["algorithm"] == "auto-mtf-1"
