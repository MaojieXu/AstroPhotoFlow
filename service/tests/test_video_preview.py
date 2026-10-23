import shutil
import struct
import subprocess

import numpy as np
import pytest

from astrophotoflow_service.video_preview import first_video_frame


def write_ser(path, color_id, width, height, depth, frame, little_endian=1):
    header=bytearray(178)
    header[:14]=b"LUCAM-RECORDER"
    struct.pack_into("<7I",header,14,0,color_id,little_endian,width,height,depth,1)
    path.write_bytes(header+frame)
    return path


@pytest.mark.parametrize("color_id,pattern",[(0,None),(8,"RGGB"),(9,"GRBG"),(10,"GBRG"),(11,"BGGR")])
def test_ser_first_mono_or_bayer_frame(color_id,pattern,tmp_path):
    raw=np.arange(24,dtype=np.uint8).tobytes()
    path=write_ser(tmp_path/(str(color_id)+".ser"),color_id,4,6,8,raw)
    image,display=first_video_frame(path,1024)
    assert image.size==(4,6)
    assert display["video_frame_index"]==0
    assert display["cfa_pattern"]==pattern


@pytest.mark.parametrize("depth,dtype", [(8, np.uint8), (16, np.uint16)])
def test_ser_rgb_and_bgr_are_decoded_from_interleaved_channels(tmp_path, depth, dtype):
    pixels=np.tile(np.array([0,127,255],dtype=dtype),(4,6,1))
    for color_id in (100,101):
        raw=pixels.astype("<u2" if depth==16 else np.uint8).tobytes()
        path=write_ser(tmp_path/(str(color_id)+"-"+str(depth)+".ser"),color_id,6,4,depth,raw)
        image,display=first_video_frame(path,1024)
        assert image.size==(6,4)
        assert display["ser_color_id"]==color_id
        assert image.mode=="RGB"
        if color_id==100:
            assert image.getpixel((0,0)) == (0,127,255)
        else:
            assert image.getpixel((0,0)) == (255,127,0)


def test_ser_honors_big_endian_16_bit_samples(tmp_path):
    pixels=np.arange(24,dtype=">u2").tobytes()
    path=write_ser(tmp_path/"big-endian.ser",0,4,6,16,pixels,little_endian=0)
    image,_=first_video_frame(path,1024)
    assert image.size==(4,6)
    assert image.getpixel((0,0))[0] < image.getpixel((1,0))[0]


@pytest.mark.parametrize("color_id,expected", [(100,(0,127,255)),(101,(255,127,0))])
def test_ser_rgb_big_endian_interleaved_channels(color_id,expected,tmp_path):
    pixels=np.tile(np.array([0,127,255],dtype=">u2"),(4,6,1))
    path=write_ser(tmp_path/(str(color_id)+"-big-endian.ser"),color_id,6,4,16,pixels.tobytes(),little_endian=0)
    image,_=first_video_frame(path,1024)
    assert image.getpixel((0,0))==expected


def test_ffmpeg_extracts_one_video_frame(tmp_path):
    ffmpeg=shutil.which("ffmpeg")
    if ffmpeg is None:pytest.skip("FFmpeg is unavailable")
    video=tmp_path/"first-frame.mp4"
    subprocess.run([
        ffmpeg,"-hide_banner","-loglevel","error","-f","lavfi","-i","color=c=red:s=32x24:r=1:d=1",
        "-frames:v","1","-y",str(video),
    ],check=True,timeout=30)
    image,display=first_video_frame(video,1024)
    assert image.size==(32,24)
    assert display["video_frame_index"]==0
