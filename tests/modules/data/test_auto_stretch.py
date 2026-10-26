import numpy as np
import pytest

from astrophotoflow.modules.data.auto_stretch import calculate_stretch, render_stretch


def test_mono_estimates_its_own_float_background_and_targets_quarter_brightness():
    pixels = np.random.default_rng(123).normal(100.01, .001, (100, 120)).astype(np.float32)
    pixels[::10, ::10] = 900
    original = pixels.copy()
    recipe = calculate_stretch(pixels)
    image = np.asarray(render_stretch(pixels, recipe))
    assert 100 < recipe["shadows"] < 100.01
    assert recipe["highlights"] == 900
    assert recipe["white_balance"] == [1]
    assert 61 <= np.median(image) <= 65
    assert calculate_stretch(pixels + 300)["shadows"] != recipe["shadows"]
    np.testing.assert_array_equal(original, pixels)


def test_rgb_white_balance_removes_cast_without_neutralizing_a_red_object():
    mono = np.random.default_rng(456).normal(100, 3, (100, 120)).astype(np.float32)
    pixels = mono[..., None] * np.asarray([2, 4, 1], dtype=np.float32)
    pixels[10:20, 10:20, 0] *= 3
    pixels[::20, ::20] = 2000
    recipe = calculate_stretch(pixels)
    image = np.asarray(render_stretch(pixels, recipe))
    assert recipe["white_balance"][0] > recipe["white_balance"][1]
    assert recipe["white_balance"][2] > recipe["white_balance"][0]
    medians = np.median(image[30:, 30:], axis=(0, 1))
    assert medians.max() - medians.min() <= 2
    assert image[15, 15, 0] > image[15, 15, 1]
    assert np.median(image[..., 1]) == pytest.approx(63, abs=3)


@pytest.mark.parametrize("pixels", [np.zeros((8, 10), dtype=np.float32),
                                    np.ones((8, 10), dtype=np.float32),
                                    np.broadcast_to([0, 100, 200], (8, 10, 3))])
def test_flat_and_zero_channel_images_have_a_finite_reproducible_recipe(pixels):
    recipe = calculate_stretch(pixels)
    assert np.isfinite([recipe["shadows"], recipe["highlights"], recipe["midtones"], *recipe["white_balance"]]).all()
    assert recipe["highlights"] > recipe["shadows"]
    assert render_stretch(pixels, recipe).tobytes() == render_stretch(pixels, recipe).tobytes()


def test_negative_and_invalid_samples_do_not_break_valid_background_statistics():
    pixels = np.linspace(-30, 80, 120, dtype=np.float32).reshape(10, 12)
    pixels[0, 0] = np.nan
    recipe = calculate_stretch(pixels)
    assert recipe["input_offset"] < 0
    assert render_stretch(pixels, recipe).getpixel((0, 0)) == (0, 0, 0)
    with pytest.raises(ValueError, match="有效像素"):
        calculate_stretch(np.full((8, 10), np.nan))
