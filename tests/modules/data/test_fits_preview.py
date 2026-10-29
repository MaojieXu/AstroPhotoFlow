from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from astrophotoflow.modules.data.fits_preview import create_preview, inspect_fits


def test_bayer_manual_cfa_and_display_presets_do_not_upscale(tmp_path):
    path = tmp_path / "手动-CFA.fits"
    primary = fits.PrimaryHDU(np.arange(1200 * 2400, dtype=np.uint16).reshape(1200, 2400))
    fits.HDUList([primary]).writeto(path)
    original = path.read_bytes()

    parsed = inspect_fits(path, "BGGR")
    assert parsed["selected_hdu"] == 0
    assert parsed["hdus"][0]["supported_kind"] == "bayer"

    thumbnail, thumb_parameters = create_preview(
        path, 0, "bayer", {"cfa_pattern": "BGGR"}, 100,
    )
    assert max(thumbnail.size) <= 100
    assert thumbnail.size == (96, 48)
    assert thumb_parameters["stretch"] == "percentile_1_99"
    assert thumb_parameters["cfa_pattern"] == "BGGR"
    assert path.read_bytes() == original


def test_first_supported_hdu_is_fixed_when_preview_generation_fails(tmp_path):
    path = tmp_path / "bad-first.fits"
    first = fits.PrimaryHDU(np.full((8, 8), np.nan, dtype=np.float32))
    second = fits.ImageHDU(np.ones((8, 8), dtype=np.float32))
    fits.HDUList([first, second]).writeto(path)

    parsed = inspect_fits(path)
    assert parsed["selected_hdu"] == 0
    assert parsed["hdus"][0]["is_selected"] is True
    assert parsed["hdus"][1]["is_selected"] is False
    with pytest.raises(ValueError, match="有效像素"):
        create_preview(path, parsed["selected_hdu"], "mono", {}, 100)


def test_explicitly_labeled_rgb_channel_axis_is_supported(tmp_path):
    path = tmp_path / "rgb.fits"
    primary = fits.PrimaryHDU()
    rgb = fits.ImageHDU(np.ones((3, 20, 30), dtype=np.float32))
    rgb.header["CTYPE3"] = "RGB"
    fits.HDUList([primary, rgb]).writeto(path)

    parsed = inspect_fits(path)
    assert parsed["selected_hdu"] == 1
    assert parsed["hdus"][0]["supported_kind"] is None
    image, _ = create_preview(path, 1, "rgb", {}, 100)
    assert image.size == (30, 20)


@pytest.mark.parametrize("dtype", [np.float32, np.int32])
def test_pixinsight_planar_rgb_without_ctype3_has_a_color_thumbnail(tmp_path, dtype):
    path = tmp_path / "pixinsight.fits"
    data = np.stack([np.full((20, 30), value, dtype=dtype) for value in (0, 100, 200)])
    hdu = fits.PrimaryHDU(data)
    hdu.header["PROGRAM"] = "PixInsight 1.9.4"
    hdu.header["BAYERPAT"] = "RGGB"
    hdu.writeto(path)
    original = path.read_bytes()
    parsed = inspect_fits(path)
    assert parsed["selected_hdu"] == 0
    assert parsed["hdus"][0]["supported_kind"] == "rgb"
    image, display = create_preview(path, 0, "rgb", {"cfa_pattern": "RGGB"}, 100)
    assert image.size == (30, 20)
    red, green, blue = image.getpixel((10, 10))
    assert red < green < blue
    assert display["cfa_pattern"] is None
    assert path.read_bytes() == original


@pytest.mark.parametrize("program,axis3", [("", ""), ("Other Program", ""), ("PixInsight 1.9.4", "FREQ")])
def test_unidentified_or_explicit_scientific_cube_is_not_assumed_rgb(tmp_path, program, axis3):
    path = tmp_path / "cube.fits"
    hdu = fits.PrimaryHDU(np.ones((3, 20, 30), dtype=np.float32))
    hdu.header["PROGRAM"] = program
    if axis3:
        hdu.header["CTYPE3"] = axis3
    hdu.writeto(path)
    assert inspect_fits(path)["selected_hdu"] is None


def test_table_hdu_before_image_is_not_selected_as_a_supported_image(tmp_path):
    path = tmp_path / "table-before-image.fits"
    primary = fits.PrimaryHDU()
    table = fits.BinTableHDU.from_columns([fits.Column(name="VALUE", format="J", array=[1, 2])])
    image_hdu = fits.ImageHDU(np.ones((8, 10), dtype=np.float32))
    fits.HDUList([primary, table, image_hdu]).writeto(path)

    parsed = inspect_fits(path)
    assert parsed["selected_hdu"] == 2
    assert parsed["hdus"][1]["supported_kind"] is None
    assert parsed["hdus"][2]["supported_kind"] == "mono"


def test_two_dimensional_image_without_cfa_is_previewed_as_mono(tmp_path):
    path = tmp_path / "mono.fits"
    fits.PrimaryHDU(np.arange(48, dtype=np.float32).reshape(6, 8)).writeto(path)
    parsed = inspect_fits(path)
    assert parsed["hdus"][0]["supported_kind"] == "mono"
    image, _ = create_preview(path, 0, "mono", {}, 100)
    assert image.size == (8, 6)


def test_float_image_keeps_its_fractional_stretch_range(tmp_path):
    path = tmp_path / "fractional.fits"
    fits.PrimaryHDU(np.linspace(0, 1, 100, dtype=np.float32).reshape(10, 10)).writeto(path)
    image, display = create_preview(path, 0, "mono", {}, 100)
    assert display["stretch_high"] < 1
    assert image.getpixel((9, 9))[0] == 255


@pytest.mark.parametrize("pattern,kind", [("XTRANS","xtrans"),("QUAD_BAYER","quad_bayer")])
def test_non_bayer_cfa_is_recorded_without_grayscale_demosaic(tmp_path, pattern, kind):
    path=tmp_path/(pattern+'.fits')
    hdu=fits.PrimaryHDU(np.arange(64,dtype=np.uint16).reshape(8,8))
    hdu.header['BAYERPAT']=pattern
    fits.HDUList([hdu]).writeto(path)
    parsed=inspect_fits(path)
    assert parsed['hdus'][0]['supported_kind']==kind
    with pytest.raises(ValueError,match='暂不支持'):
        create_preview(path,0,kind,{},100)


def test_manual_cfa_choice_overrides_conflicting_fits_header(tmp_path):
    path=tmp_path/'manual-cfa.fits'
    hdu=fits.PrimaryHDU(np.arange(64,dtype=np.uint16).reshape(8,8))
    hdu.header['BAYERPAT']='XTRANS'
    hdu.writeto(path)
    parsed=inspect_fits(path,'RGGB')
    assert parsed['hdus'][0]['supported_kind']=='bayer'
    image,_=create_preview(path,0,'bayer',{'cfa_pattern':'RGGB'},100)
    assert image.size==(8,8)


@pytest.mark.parametrize("layout", ["float", "uint16", "scaled", "bayer", "planar", "interleaved", "compressed"])
def test_sampled_rows_match_previous_scalar_section_samples_and_preview(tmp_path, layout):
    from PIL import Image
    from astrophotoflow.modules.data.fits_preview import _bayer_demosaic, _display, stretch_bounds
    path = tmp_path / f"{layout}.fits"
    values = np.arange(99 * 148, dtype=np.float32).reshape(99, 148) / 100
    kind, parameters = "mono", {}
    if layout == "uint16":
        hdu = fits.PrimaryHDU((values * 100).astype(np.uint16))
    elif layout == "scaled":
        hdu = fits.PrimaryHDU(values)
        hdu.scale("int16", bscale=.25, bzero=20)
    elif layout == "planar":
        hdu = fits.PrimaryHDU(np.stack([values, values + 10, values + 20]))
        hdu.header["CTYPE3"] = "RGB"
        kind = "rgb"
    elif layout == "interleaved":
        hdu = fits.PrimaryHDU(np.stack([values, values + 10, values + 20], axis=-1))
        hdu.header["CTYPE1"] = "RGB"
        kind = "rgb"
    elif layout == "compressed":
        hdu = fits.CompImageHDU(values)
    else:
        hdu = fits.PrimaryHDU(values)
    if layout == "bayer":
        kind, parameters = "bayer", {"cfa_pattern": "RGGB"}
        hdu.header["BAYERPAT"] = "RGGB"
        hdu.header["XBAYROFF"], hdu.header["YBAYROFF"] = 1, 1
    if layout == "compressed":
        fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(path)
        index = 1
    else:
        hdu.writeto(path)
        index = 0
    original_bytes = path.read_bytes()
    with fits.open(path, memmap=False, lazy_load_hdus=True) as hdus:
        source = hdus[index]
        stride = (max(source.shape[-2:]) + 30) // 31
        if kind == "bayer" and stride % 2 == 0:
            stride += 1
        # The previous implementation's exact Section expression is the oracle.
        if layout == "planar":
            sample = np.moveaxis(np.asarray(source.section[:, ::stride, ::stride], dtype=np.float32), 0, -1)
        elif layout == "interleaved":
            sample = np.asarray(source.section[::stride, ::stride, :], dtype=np.float32)
        else:
            sample = np.asarray(source.section[::stride, ::stride], dtype=np.float32)
        if kind == "bayer":
            sample = _bayer_demosaic(sample, "RGGB", 1, 1, stride)
    low, high = stretch_bounds(sample)
    expected = _display(sample, (low, high))
    expected.thumbnail((31, 31), Image.Resampling.LANCZOS)
    actual, display = create_preview(path, index, kind, parameters, 31)
    assert actual.size == expected.size
    assert actual.tobytes() == expected.tobytes()
    assert display["stretch_low"] == low
    assert display["stretch_high"] == high
    assert display["downsample_stride"] == stride
    assert path.read_bytes() == original_bytes


def test_sampled_rows_avoid_per_pixel_fits_reads(tmp_path, monkeypatch):
    path = tmp_path / "reads.fits"
    fits.PrimaryHDU(np.arange(99 * 148, dtype=np.float32).reshape(99, 148)).writeto(path)
    original = fits.PrimaryHDU._get_scaled_image_data
    calls = []
    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(fits.PrimaryHDU, "_get_scaled_image_data", counted)
    with fits.open(path, memmap=False) as hdus:
        np.asarray(hdus[0].section[::5, ::5])
    old_count = len(calls)
    calls.clear()
    create_preview(path, 0, "mono", {}, 31)
    assert len(calls) == 20
    assert old_count == 600


@pytest.mark.parametrize("color", [False, True])
def test_percentile_statistics_are_bounded_and_keep_finite_zero_samples(color, monkeypatch):
    from astrophotoflow.modules.data.fits_preview import stretch_bounds
    from astrophotoflow.modules.data.auto_stretch import STATISTICS_SAMPLES, sample_statistics

    pixels = np.arange(1025 * 777, dtype=np.float64).reshape(1025, 777)
    if color:
        pixels = np.repeat(pixels[..., None], 3, axis=-1)
    pixels[5, 5] = np.nan
    original = pixels.copy()
    sampled = sample_statistics(pixels)
    finite = sampled[np.isfinite(sampled)]
    expected = np.percentile(finite, (1, 99))
    sizes = []
    percentile = np.percentile

    def counted(values, *args, **kwargs):
        sizes.append(values.size)
        return percentile(values, *args, **kwargs)

    monkeypatch.setattr(np, "percentile", counted)
    assert stretch_bounds(pixels) == pytest.approx(expected)
    assert sizes == [finite.size]
    assert sizes[0] <= STATISTICS_SAMPLES * (3 if color else 1)
    np.testing.assert_array_equal(pixels, original)


@pytest.mark.parametrize("layout", ["mono", "uint16", "scaled", "planar", "interleaved", "compressed"])
def test_fits_statistics_sample_original_spatial_strata_with_row_reads(tmp_path, monkeypatch, layout):
    from astrophotoflow.modules.data.auto_stretch import sample_statistics, statistics_indices
    from astrophotoflow.modules.data.fits_preview import read_stretch_pixels

    values = np.arange(1025 * 777, dtype=np.float32).reshape(1025, 777) / 100
    kind = "mono"
    if layout == "uint16":
        values = values.astype(np.uint16)
    hdu = fits.CompImageHDU(values) if layout == "compressed" else fits.PrimaryHDU(values)
    if layout == "scaled":
        hdu.scale("int16", bscale=.5, bzero=1000)
    elif layout in {"planar", "interleaved"}:
        values = np.stack([values, values + 10, values + 20], axis=-1)
        hdu = fits.PrimaryHDU(np.moveaxis(values, -1, 0) if layout == "planar" else values)
        hdu.header["CTYPE3" if layout == "planar" else "CTYPE1"] = "RGB"
        kind = "rgb"
    path = tmp_path / f"{layout}.fits"
    index = 1 if layout == "compressed" else 0
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(path) if index else hdu.writeto(path)
    original = path.read_bytes()
    with fits.open(path, memmap=False) as hdus:
        expected_pixels = hdus[index].data
        if layout == "planar":
            expected_pixels = np.moveaxis(expected_pixels, 0, -1)
        expected = sample_statistics(expected_pixels)
    calls = []
    read = fits.ImageHDU._get_scaled_image_data if index else fits.PrimaryHDU._get_scaled_image_data

    def counted(*args, **kwargs):
        calls.append(1)
        return read(*args, **kwargs)

    if layout != "compressed":
        monkeypatch.setattr(fits.PrimaryHDU, "_get_scaled_image_data", counted)
    actual = read_stretch_pixels(path, index, kind, {})
    np.testing.assert_array_equal(actual, expected)
    if layout != "compressed":
        rows, _ = statistics_indices(1025, 777)
        assert len(calls) <= len(rows) * (3 if kind == "rgb" else 1)
    assert path.read_bytes() == original


@pytest.mark.parametrize("pattern", ["RGGB", "BGGR", "GRBG", "GBRG"])
def test_bayer_statistics_keep_rgb_cells_and_offsets_together(tmp_path, pattern):
    from astrophotoflow.modules.data.auto_stretch import sample_statistics
    from astrophotoflow.modules.data.fits_preview import read_stretch_pixels

    values = np.arange(600 * 800, dtype=np.float32).reshape(600, 800)
    mosaic = np.empty((1200, 1600), dtype=np.float32)
    gains = {"R": 1, "G": 2, "B": 4}
    for dy in range(2):
        for dx in range(2):
            mosaic[dy::2, dx::2] = values * gains[pattern[((dy + 1) % 2) * 2 + ((dx + 1) % 2)]]
    hdu = fits.PrimaryHDU(mosaic)
    hdu.header["BAYERPAT"] = pattern
    hdu.header["XBAYROFF"] = hdu.header["YBAYROFF"] = 1
    path = tmp_path / f"{pattern}.fits"
    hdu.writeto(path)
    original = path.read_bytes()
    expected = sample_statistics(values[..., None] * np.array([1, 2, 4], dtype=np.float32))
    np.testing.assert_array_equal(read_stretch_pixels(path, 0, "bayer", {}), expected)
    assert path.read_bytes() == original
