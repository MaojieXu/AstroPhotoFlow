from io import BytesIO
from types import SimpleNamespace
import struct
import numpy as np
from PIL import Image
import pytest
from astrophotoflow.contracts.media import MediaSelection
from astrophotoflow.modules.data.formats import video as codec_formats_video
from astrophotoflow.modules.data.media import playback as codec_media_playback
from astrophotoflow.modules.data.formats.source import PixelSource
from astrophotoflow.modules.data.formats.ser import ser_info
from astrophotoflow.modules.data.media.cache import MediaCache
import json

def test_vfr_frame_timestamps_are_not_calculated_from_average_fps():
    log = 'config in time_base: 1/1000000\n' + '\n'.join((f'[Parsed_showinfo_0] n: {index:3d} pts: {round(time * 1000000.0)} pts_time:{time}' for index, time in enumerate([0, 0.041, 0.147, 0.181])))
    assert codec_formats_video.frame_times(log) == [(0, 0.0), (1, 0.041), (2, 0.147), (3, 0.181)]

def test_pause_reads_original_frame_and_rejects_a_different_presented_timestamp(tmp_path, monkeypatch):
    pixels = np.full((83, 127, 3), [20, 40, 80], dtype=np.uint8)
    image = BytesIO()
    Image.fromarray(pixels).save(image, format='PNG')
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout=image.getvalue(), stderr=b'config in time_base: 1/1000000\n[showinfo] n: 0 pts: 147000 pts_time:0.147')
    monkeypatch.setattr(codec_formats_video, 'ffmpeg', lambda: 'existing-ffmpeg')
    monkeypatch.setattr(codec_formats_video.subprocess, 'run', run)
    original = tmp_path / 'source.mp4'
    original.write_bytes(b'original compressed video')
    folder = tmp_path / 'frame'
    folder.mkdir()
    target, width, height, timestamp = codec_formats_video.extract_frame(original, MediaSelection(media_time=0.147), folder, lambda _: None)
    assert (width, height, timestamp) == (127, 83, 0.147)
    np.testing.assert_array_equal(np.load(target, allow_pickle=False), pixels)
    assert 'trim=start=0.147000000,showinfo' in commands[0]
    assert not any(('scale=' in item for item in commands[0]))
    with pytest.raises(ValueError, match='精确对应'):
        codec_formats_video.extract_frame(original, MediaSelection(media_time=0.1489 + 0.01), folder, lambda _: None)
    assert original.read_bytes() == b'original compressed video'

def test_ser_frames_are_directly_addressed_with_real_geometry_and_timestamps(tmp_path):
    width, height, count = (17, 13, 3)
    header = bytearray(178)
    header[:14] = b'LUCAM-RECORDER'
    header[14:42] = struct.pack('<7I', 0, 0, 1, width, height, 16, count)
    frames = np.arange(count * height * width, dtype='<u2').reshape(count, height, width)
    stamps = np.array([10000000, 10041000, 10147000], dtype='<u8')
    path = tmp_path / 'sequence.ser'
    path.write_bytes(header + frames.tobytes() + stamps.tobytes())
    info = ser_info(path)
    assert info.count == 3
    np.testing.assert_allclose(info.times, [0, 0.0041, 0.0147])
    reader = PixelSource(path, 'video', MediaSelection(frame_index=2), {}, tmp_path, lambda _: None)
    assert reader.dimensions() == (width, height)
    np.testing.assert_array_equal(reader.read((2, 3, 10, 9)), frames[2, 3:9, 2:10])

def test_video_header_dimensions_honor_rotation_without_ffprobe(monkeypatch):
    result = SimpleNamespace(returncode=0, stderr=b'Duration: 00:00:02.15\n Stream #0:0: Video: h264, yuv420p, 1920x1080\n displaymatrix: rotation of -90.00 degrees\nStream mapping:')
    monkeypatch.setattr(codec_formats_video, 'ffmpeg', lambda: 'existing-ffmpeg')
    monkeypatch.setattr(codec_formats_video.subprocess, 'run', lambda *args, **kwargs: result)
    assert codec_formats_video.video_info('portrait.mov') == (1080, 1920, 2.15)

@pytest.mark.parametrize('timed', [False, True])
def test_ser_proxy_preserves_frame_mapping_and_timestamps_without_preextracting_frames(tmp_path, monkeypatch, timed):
    header = bytearray(178)
    header[:14] = b'LUCAM-RECORDER'
    header[14:42] = struct.pack('<7I', 0, 0, 1, 16, 12, 8, 3)
    frames = np.arange(3 * 16 * 12, dtype=np.uint8).reshape(3, 12, 16)
    times = np.array([10000000, 10041000, 10147000], dtype='<u8')
    original = tmp_path / 'video.ser'
    original.write_bytes(header + frames.tobytes() + (times.tobytes() if timed else b''))
    folder = tmp_path / 'previews' / 'version' / 'media' / 'proxy'
    folder.mkdir(parents=True)
    seen = {'chunks': []}

    class Input:

        def write(self, data):
            seen['chunks'].append(data)

        def close(self):
            pass

    class Encoder:
        returncode = 0
        stdin = Input()

        def __init__(self, command, **kwargs):
            seen['command'] = command
            if timed:
                seen['timing'] = (folder / 'ser-pts.cmd').read_text()
            from pathlib import Path
            Path(command[-1]).write_bytes(b'playback proxy')
            denominator = 10000000 if timed else 10
            points = [0, 41000, 147000] if timed else [0, 1, 2]
            log = f'config in time_base: 1/{denominator}\n' + '\n'.join((f'n: {i} pts: {point} pts_time:0' for i, point in enumerate(points)))
            kwargs['stderr'].write(log.encode())

        def poll(self):
            return 0

        def wait(self, **kwargs):
            return 0
    monkeypatch.setattr(codec_formats_video, 'ffmpeg', lambda: 'existing-ffmpeg')
    monkeypatch.setattr(codec_formats_video.subprocess, 'Popen', Encoder)
    target, note = codec_media_playback.make_proxy(original, folder, MediaCache(tmp_path), {}, {'stretch_low': 0, 'stretch_high': 255})
    assert target.read_bytes() == b'playback proxy'
    mapping = json.loads((folder / 'frames.json').read_text())
    assert [frame['index'] for frame in mapping] == [0, 1, 2]
    np.testing.assert_allclose([frame['time'] for frame in mapping], [0, 0.0041, 0.0147] if timed else [0, 0.1, 0.2])
    assert len(seen['chunks']) == 3
    assert not list(folder.glob('*.png'))
    assert not (folder / 'ser-pts.cmd').exists()
    if timed:
        assert '0.004100000/TB' in seen['timing']
    else:
        assert '10fps' in note
