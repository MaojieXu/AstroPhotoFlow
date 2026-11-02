from astrophotoflow.modules.data.formats import pixels as codec_formats_pixels
import numpy as np
import pytest
from astropy.io import fits
from PIL import Image

from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.contracts.media import MediaSelection
from astrophotoflow.modules.data.public import check_output, render_output_preview


def settings(tmp_path):
    return Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)


def test_declared_planar_colour_is_interpreted_without_rewriting_scientific_bytes(tmp_path):
    source = tmp_path / 'rgb.fit'
    fits.writeto(source, np.stack([np.full((9, 11), value, dtype=np.float32) for value in [.2, .5, .8]]))
    original = source.read_bytes()
    checked = check_output(settings(tmp_path), run_directory=tmp_path, path=source, expected_format='fits',
                           colour_layout='planar', expected_frames=1)
    assert checked.scientific_metadata['selected_hdu'] == 0
    assert checked.scientific_metadata['frame_count'] == 1
    preview = tmp_path / 'preview.jpg'
    render_output_preview(checked, preview, max_edge=1024, auto_stretch=False)
    with Image.open(preview) as image:
        np.testing.assert_allclose(np.asarray(image)[0, 0], [51, 127, 204], atol=3)
    assert source.read_bytes() == original
    assert 'CTYPE3' not in fits.getheader(source)


def test_explicit_spectral_axis_cannot_be_relabelled_as_rgb(tmp_path):
    source = tmp_path / 'spectrum.fit'
    fits.writeto(source, np.zeros((3, 7, 9), dtype=np.float32), fits.Header({'CTYPE3': 'WAVE'}))
    before = source.read_bytes()
    with pytest.raises(ApiError, match='FITS'):
        check_output(settings(tmp_path), run_directory=tmp_path, path=source, expected_format='fits', colour_layout='planar')
    assert source.read_bytes() == before


def test_fits_sequence_checks_all_image_hdus_and_expected_frame_count(tmp_path):
    source = tmp_path / 'sequence.fit'
    fits.HDUList([fits.PrimaryHDU(np.zeros((5, 7), dtype=np.float32)),
                  fits.ImageHDU(np.ones((5, 7), dtype=np.float32))]).writeto(source)
    checked = check_output(settings(tmp_path), run_directory=tmp_path, path=source, expected_format='fits', expected_frames=2)
    assert checked.scientific_metadata['frame_count'] == 2
    with pytest.raises(ApiError, match='实际帧数'):
        check_output(settings(tmp_path), run_directory=tmp_path, path=source, expected_format='fits', expected_frames=1)
    source.write_bytes(source.read_bytes()[:-2880])
    with pytest.raises(ApiError, match='FITS'):
        check_output(settings(tmp_path), run_directory=tmp_path, path=source, expected_format='fits', expected_frames=2)


def test_empty_bad_pixel_map_requires_an_explicit_non_scientific_declaration(tmp_path):
    source = tmp_path / 'empty.lst'; source.write_bytes(b'')
    with pytest.raises(ApiError, match='为空'):
        check_output(settings(tmp_path), run_directory=tmp_path, path=source, expected_format='other')
    checked = check_output(settings(tmp_path), run_directory=tmp_path, path=source, expected_format='other', allow_empty=True)
    assert checked.byte_size == 0 and checked.content_hash and checked.mtime_ns is not None
    bad_fits = tmp_path / 'empty.fit'; bad_fits.write_bytes(b'')
    with pytest.raises(ApiError):
        check_output(settings(tmp_path), run_directory=tmp_path, path=bad_fits, expected_format='fits', allow_empty=True)


def test_display_threshold_zero_is_preserved_and_invalid_ranges_are_rejected():
    assert MediaSelection(display_range=(0, 1)).display_range == (0, 1)
    assert MediaSelection(display_range=None).display_range is None
    for limits in [(1, 1), (1, 0), (0, float('inf')), (float('nan'), 1)]:
        with pytest.raises(ValueError):
            MediaSelection(display_range=limits)


def test_display_thresholds_round_trip_through_json_state_without_coercing_strings():
    selection = MediaSelection(display_range=(0, 1))
    assert MediaSelection.model_validate(selection.model_dump(mode='json')) == selection
    with pytest.raises(ValueError):
        MediaSelection.model_validate({'display_range': ['0', '1']})


def test_embedded_icc_profile_is_not_counted_as_a_scientific_frame(tmp_path):
    source = tmp_path/'colour.fit'
    pixels = np.full((3, 5, 7), .25, dtype=np.float32)
    fits.HDUList([fits.PrimaryHDU(pixels, fits.Header({'CTYPE3': 'RGB'})),
                  fits.ImageHDU(np.arange(128, dtype=np.uint8), name='ICCProfile')]).writeto(source)
    original = source.read_bytes()
    checked = check_output(settings(tmp_path), run_directory=tmp_path, path=source, expected_format='fits',
                           colour_layout='planar', expected_frames=1)
    assert checked.scientific_metadata['frame_count'] == 1
    assert checked.scientific_metadata['hdu_count'] == 2
    assert source.read_bytes() == original
