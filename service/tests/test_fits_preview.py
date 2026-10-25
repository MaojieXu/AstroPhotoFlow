from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from astrophotoflow_service.fits_preview import create_preview, inspect_fits


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


def test_only_explicitly_labeled_rgb_channel_axis_is_supported(tmp_path):
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
