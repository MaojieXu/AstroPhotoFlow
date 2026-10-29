from pathlib import Path
from types import SimpleNamespace

from astropy.io import fits
import numpy as np
from PIL import Image
import pytest
from xisf import XISF

from astrophotoflow.contracts.media import MediaSelection
from astrophotoflow.modules.data import media_sources
from astrophotoflow.modules.data.media_sources import PixelSource, numpy_arrays, select_array


def source(tmp_path, path, category, selection=None, parameters=None):
    folder = tmp_path / "derived"
    folder.mkdir(exist_ok=True)
    return PixelSource(path, category, selection or MediaSelection(), parameters or {}, folder, lambda _: None)


@pytest.mark.parametrize("kind", ["mono", "planar", "interleaved", "compressed", "scaled"])
def test_fits_reads_original_region_with_odd_dimensions_without_modifying_source(tmp_path, kind):
    values = np.arange(519 * 523, dtype=np.float32).reshape(519, 523)
    if kind in {"planar", "interleaved"}:
        values = np.stack([values, values + 1, values + 2], axis=0 if kind == "planar" else -1)
    path = tmp_path / "frame.fits"
    hdu = fits.CompImageHDU(values) if kind == "compressed" else fits.PrimaryHDU(values)
    if kind in {"planar", "interleaved"}:
        hdu.header["CTYPE3" if kind == "planar" else "CTYPE1"] = "RGB"
    if kind == "scaled":
        hdu = fits.PrimaryHDU(values.astype(np.int16))
        hdu.header["BSCALE"], hdu.header["BZERO"] = 0.5, 100
    hdu.writeto(path)
    original = path.read_bytes()
    reader = source(tmp_path, path, "fits", MediaSelection(hdu_index=1 if kind == "compressed" else 0))
    assert reader.dimensions() == (523, 519)
    result = reader.read((501, 497, 523, 519))
    expected = np.moveaxis(values, 0, -1) if kind == "planar" else values
    if kind == "scaled":
        expected = values.astype(np.int16) * .5 + 100
    np.testing.assert_array_equal(result, expected[497:519, 501:523])
    assert path.read_bytes() == original


@pytest.mark.parametrize("pattern", ["RGGB", "BGGR", "GRBG", "GBRG"])
def test_bayer_halo_regions_match_full_frame_interior(tmp_path, pattern):
    path = tmp_path / "color.fits"
    hdu = fits.PrimaryHDU(np.random.default_rng(3).uniform(20, 1000, (530, 550)).astype(np.float32))
    hdu.header["BAYERPAT"] = pattern
    hdu.header["XBAYROFF"] = 1
    hdu.writeto(path)
    reader = source(tmp_path, path, "fits")
    reader.dimensions()
    full = reader.read((0, 0, 550, 530))
    local = reader.read((505, 503, 525, 523))
    np.testing.assert_allclose(local[3:-3, 3:-3], full[506:520, 508:522])


def test_npz_headers_do_not_load_payload_and_explicit_axes_preserve_zero(tmp_path, monkeypatch):
    path = tmp_path / "arrays.npz"
    values = np.arange(2 * 7 * 9 * 3, dtype=np.float32).reshape(2, 7, 9, 3)
    np.savez_compressed(path, science=values, labels=np.array(["not an image"]))
    original = np.load
    monkeypatch.setattr(np, "load", lambda *args, **kwargs: pytest.fail("header inspection loaded pixels"))
    descriptors = numpy_arrays(path)
    assert [(item.key, item.numeric) for item in descriptors] == [("science", True), ("labels", False)]
    monkeypatch.setattr(np, "load", original)
    selection = MediaSelection(array_key="science", x_axis=2, y_axis=1, channel_axis=3, slices={"0": 0})
    reader = source(tmp_path, path, "numpy", selection)
    assert reader.dimensions() == (9, 7)
    np.testing.assert_array_equal(reader.read((0, 0, 9, 7)), values[0])


def test_multidimensional_array_requires_axes_and_rejects_invalid_slices():
    with pytest.raises(ValueError, match="请选择"):
        select_array(np.zeros((4, 6, 8, 2)), MediaSelection())
    with pytest.raises(ValueError, match="切片索引"):
        select_array(np.zeros((4, 6, 8)), MediaSelection(x_axis=2, y_axis=1, slices={"0": 4}))
    with pytest.raises(ValueError, match="实数"):
        select_array(np.ones((6, 8), dtype=complex), MediaSelection())


@pytest.mark.parametrize("category", ["image", "xisf"])
def test_full_decode_is_cached_once_and_region_reads_keep_source_resolution(tmp_path, category, monkeypatch):
    values = np.random.default_rng(1).integers(0, 255, (671, 1313, 3), dtype=np.uint8)
    path = tmp_path / ("frame.png" if category == "image" else "frame.xisf")
    if category == "image":
        Image.fromarray(values).save(path)
    else:
        XISF.write(str(path), values)
    reader = source(tmp_path, path, category)
    assert reader.dimensions() == (1313, 671)
    if category == "image":
        monkeypatch.setattr(media_sources.Image, "open", lambda *args: pytest.fail("source image decoded twice"))
    else:
        monkeypatch.setattr(media_sources, "XISF", lambda *args: pytest.fail("XISF decoded twice"))
    np.testing.assert_array_equal(reader.read((1200, 600, 1313, 671)), values[600:, 1200:])


def test_raw_uses_full_postprocess_without_embedded_thumbnail(tmp_path, monkeypatch):
    seen = {}
    pixels = np.full((541, 1029, 3), 64, dtype=np.uint8)
    class Raw:
        sizes = SimpleNamespace(width=1029, height=541)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def postprocess(self, **options):
            seen.update(options)
            return pixels
    monkeypatch.setattr(media_sources.rawpy, "imread", lambda path: Raw())
    path = tmp_path / "camera.cr3"
    reader = source(tmp_path, path, "raw")
    assert reader.dimensions() == (1029, 541)
    assert seen["half_size"] is False
    np.testing.assert_array_equal(reader.read((1000, 500, 1029, 541)), pixels[500:, 1000:])


@pytest.mark.parametrize("kind", ["mono", "planar", "interleaved", "compressed", "scaled"])
@pytest.mark.parametrize("step", [1, 3, 5])
def test_strided_fits_reads_contiguous_bounded_strips(tmp_path, monkeypatch, kind, step):
    from contextlib import contextmanager
    values = np.arange(53 * 71, dtype=np.float32).reshape(53, 71)
    if kind in {"planar", "interleaved"}:
        values = np.stack([values, values + 2, values + 4], axis=0 if kind == "planar" else -1)
    hdu = fits.CompImageHDU(values) if kind == "compressed" else fits.PrimaryHDU(values)
    if kind in {"planar", "interleaved"}:
        hdu.header["CTYPE3" if kind == "planar" else "CTYPE1"] = "RGB"
    if kind == "scaled":
        hdu = fits.PrimaryHDU(values.astype(np.int16))
        hdu.header["BSCALE"], hdu.header["BZERO"] = .5, 100
    path = tmp_path / "strip.fits"
    hdu.writeto(path)
    original = path.read_bytes()
    reader = source(tmp_path, path, "fits", MediaSelection(hdu_index=int(kind == "compressed")))
    budget = 71 * 8 * 7
    monkeypatch.setattr(media_sources, "FITS_STRIP_BYTES", budget)
    calls = []
    native_pixels = reader.pixels
    @contextmanager
    def pixels():
        with native_pixels() as data:
            class Section:
                def __getitem__(self, key):
                    assert all(not isinstance(part, slice) or part.step in (None, 1) for part in key)
                    strip = data.section[key]
                    assert strip.nbytes <= budget
                    calls.append(key)
                    return strip
            yield SimpleNamespace(shape=data.shape, header=data.header, section=Section())
    monkeypatch.setattr(reader, "pixels", pixels)
    result = reader.read((3, 5, 68, 51), step)
    expected = np.moveaxis(values, 0, -1) if kind == "planar" else values
    if kind == "scaled":
        expected = values.astype(np.int16) * .5 + 100
    np.testing.assert_array_equal(result, expected[5:51:step, 3:68:step])
    assert len(calls) <= 3 * 23
    assert path.read_bytes() == original


def test_fits_read_stops_at_strip_boundary(tmp_path, monkeypatch):
    from concurrent.futures import CancelledError
    path = tmp_path / "cancel.fits"
    fits.PrimaryHDU(np.ones((100, 60), dtype=np.float32)).writeto(path)
    reader = source(tmp_path, path, "fits")
    monkeypatch.setattr(media_sources, "FITS_STRIP_BYTES", 60 * 8 * 4)
    checks = []
    def cancel():
        checks.append(True)
        if len(checks) == 4:
            raise CancelledError("closed")
    reader.check_cancel = cancel
    with pytest.raises(CancelledError, match="closed"):
        reader.read((0, 0, 60, 100), 3)
    assert len(checks) == 4
