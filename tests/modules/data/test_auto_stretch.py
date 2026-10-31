import numpy as np
import pytest

from astrophotoflow.modules.data.auto_stretch import STATISTICS_SAMPLES, calculate_stretch, render_stretch, sample_statistics, statistics_indices


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


def test_preserving_rgb_uses_one_curve_without_white_balance():
    mono = np.random.default_rng(1).normal(.01, .001, (80, 90)).astype(np.float32)
    pixels = mono[..., None] * [1, 2, 1]
    recipe = calculate_stretch(pixels, balance_rgb=False)
    assert recipe['white_balance'] == [1, 1, 1]
    medians = np.median(np.asarray(render_stretch(pixels, recipe)), axis=(0, 1))
    assert medians[1] > medians[0] == medians[2]


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


@pytest.mark.parametrize("color", [False, True])
def test_large_photo_statistics_use_deterministic_stratified_random_source_samples(color, monkeypatch):
    pixels = np.arange(1025 * 777, dtype=np.float64).reshape(1025, 777) + 100
    if color:
        pixels = pixels[..., None] * np.array([1, 2, 4])
    original = pixels.copy()
    sample = sample_statistics(pixels)
    rows, columns = statistics_indices(1025, 777)
    assert sample.shape == (*columns.shape, 3) if color else sample.shape == columns.shape
    assert sample.dtype == np.float32
    np.testing.assert_array_equal(sample, pixels[rows[:, None], columns].astype(np.float32))
    np.testing.assert_array_equal(sample_statistics(pixels), sample)
    assert columns.size <= STATISTICS_SAMPLES
    assert np.unique(np.diff(rows)).size > 1
    medians = []
    median = np.median

    def counted(values, *args, **kwargs):
        medians.append(values.shape[0])
        return median(values, *args, **kwargs)

    monkeypatch.setattr(np, "median", counted)
    recipe = calculate_stretch(pixels)
    assert medians and max(medians) <= STATISTICS_SAMPLES
    assert recipe == calculate_stretch(sample)
    assert render_stretch(pixels, recipe).size == (777, 1025)
    np.testing.assert_array_equal(pixels, original)


def test_fast_stretch_keeps_rgb_channels_together_and_ignores_invalid_samples():
    pixels = np.broadcast_to([10, 20, 40], (1025, 777, 3)).astype(np.float32).copy()
    pixels[0, 0, 1] = np.nan
    recipe = calculate_stretch(pixels)
    assert recipe["white_balance"] == pytest.approx([7 / 3, 7 / 6, 7 / 12])
    assert np.isfinite([recipe["shadows"], recipe["highlights"], recipe["midtones"]]).all()


@pytest.mark.parametrize("shape", [(8, 10), (1, 300000), (300000, 1), (6000, 4000)])
def test_stratified_coordinates_cover_all_spatial_strata_without_exceeding_budget(shape):
    height, width = shape
    rows, columns = statistics_indices(height, width)
    row_edges = np.linspace(0, height, len(rows) + 1, dtype=np.int64)
    column_edges = np.linspace(0, width, columns.shape[1] + 1, dtype=np.int64)
    assert columns.size <= STATISTICS_SAMPLES
    assert ((rows >= row_edges[:-1]) & (rows < row_edges[1:])).all()
    assert ((columns >= column_edges[:-1]) & (columns < column_edges[1:])).all()


def test_randomized_sampling_does_not_lock_onto_periodic_pixel_phase():
    pixels = np.broadcast_to(np.where(np.arange(2048) % 8 == 0, 1000, 10), (2048, 2048))
    sample = sample_statistics(pixels)
    assert (sample == 1000).mean() == pytest.approx(1 / 8, abs=.01)
    assert np.median(sample) == 10
