"""Unit tests for video validation service."""
import pathlib
import struct

import pytest

from app.core.errors import AppError
from app.services.video_service import (
    MAX_SPLASH_VIDEO_BYTES,
    validate_mp4_video,
    validate_mp4_video_ffprobe,
    validate_mp4_video_pure_python,
)

FIXTURE_PATH = pathlib.Path(__file__).parent / "fixtures" / "sample_splash.mp4"


def make_mp4(
    duration_sec: float = 2.5,
    timescale: int = 1000,
    width: int = 1080,
    height: int = 1920,
    codec: bytes = b"avc1",
    include_audio: bool = False,
    include_mdat: bool = True,
    mvhd_version: int = 0,
    truncate_mvhd_bytes: int = 0,
    extra_bytes: int = 0,
) -> bytes:
    ftyp_payload = b"isom\x00\x00\x02\x00isomiso2avc1mp41"
    ftyp = struct.pack(">I4s", 8 + len(ftyp_payload), b"ftyp") + ftyp_payload
    duration_val = int(duration_sec * timescale)

    if mvhd_version == 0:
        mvhd_payload = struct.pack(">BBBBIIII", 0, 0, 0, 0, 0, 0, timescale, duration_val) + b"\x00" * 80
    else:
        # Version 1 (64-bit creation, modification, duration)
        mvhd_payload = struct.pack(">BBBBQQIQ", 1, 0, 0, 0, 0, 0, timescale, duration_val) + b"\x00" * 80

    if truncate_mvhd_bytes > 0:
        mvhd_payload = mvhd_payload[:-truncate_mvhd_bytes]

    mvhd = struct.pack(">I4s", 8 + len(mvhd_payload), b"mvhd") + mvhd_payload

    tkhd_payload = (
        struct.pack(">BBBBIIIII", 0, 0, 0, 3, 0, 0, 1, 0, duration_val)
        + b"\x00" * 8
        + b"\x00" * 8
        + b"\x00" * 36
        + struct.pack(">II", width << 16, height << 16)
    )
    tkhd = struct.pack(">I4s", 8 + len(tkhd_payload), b"tkhd") + tkhd_payload
    hdlr_payload = struct.pack(">BBBB4s4s", 0, 0, 0, 0, b"\x00\x00\x00\x00", b"vide") + b"\x00" * 12 + b"VideoHandler\x00"
    hdlr = struct.pack(">I4s", 8 + len(hdlr_payload), b"hdlr") + hdlr_payload
    stsd_payload = struct.pack(">BBBB", 0, 0, 0, 0) + struct.pack(">I", 1)
    avc1_payload = b"\x00" * 6 + b"\x00\x01" + b"\x00" * 16 + struct.pack(">HH", width, height) + b"\x00" * 50
    stsd_payload += struct.pack(">I4s", 8 + len(avc1_payload), codec) + avc1_payload
    stsd = struct.pack(">I4s", 8 + len(stsd_payload), b"stsd") + stsd_payload
    stbl = struct.pack(">I4s", 8 + len(stsd), b"stbl") + stsd
    minf = struct.pack(">I4s", 8 + len(stbl), b"minf") + stbl
    mdia = struct.pack(">I4s", 8 + len(hdlr) + len(minf), b"mdia") + hdlr + minf
    trak = struct.pack(">I4s", 8 + len(tkhd) + len(mdia), b"trak") + tkhd + mdia
    moov_parts = [mvhd, trak]

    if include_audio:
        audio_hdlr_payload = struct.pack(">BBBB4s4s", 0, 0, 0, 0, b"\x00\x00\x00\x00", b"soun") + b"\x00" * 12 + b"SoundHandler\x00"
        audio_hdlr = struct.pack(">I4s", 8 + len(audio_hdlr_payload), b"hdlr") + audio_hdlr_payload
        audio_mdia = struct.pack(">I4s", 8 + len(audio_hdlr), b"mdia") + audio_hdlr
        audio_trak = struct.pack(">I4s", 8 + len(audio_mdia), b"trak") + audio_mdia
        moov_parts.append(audio_trak)

    moov_payload = b"".join(moov_parts)
    moov = struct.pack(">I4s", 8 + len(moov_payload), b"moov") + moov_payload

    result = ftyp + moov

    if include_mdat:
        mdat_payload = b"\x00\x00\x00\x01\x67\x42\x00\x1f" + b"\x00" * 64
        mdat = struct.pack(">I4s", 8 + len(mdat_payload), b"mdat") + mdat_payload
        result += mdat

    if extra_bytes > 0:
        result += b"\x00" * extra_bytes
    return result


def test_real_mp4_fixture_passes_validation():
    assert FIXTURE_PATH.is_file(), f"Fixture {FIXTURE_PATH} must exist"
    data = FIXTURE_PATH.read_bytes()
    meta = validate_mp4_video(data)
    assert meta.width == 320
    assert meta.height == 240
    assert meta.duration_seconds == 1.0
    assert meta.codec == "h264"
    assert meta.file_size == len(data)


def test_mp4_without_mdat_atom_rejected():
    data = make_mp4(include_mdat=False)
    with pytest.raises(AppError) as exc_info:
        validate_mp4_video_pure_python(data)
    assert exc_info.value.status_code == 415
    assert "отсутствует секция видеоданных (mdat atom)" in exc_info.value.message


def test_mp4_mvhd_v1_valid_passes():
    data = make_mp4(duration_sec=3.0, mvhd_version=1)
    meta = validate_mp4_video_pure_python(data)
    assert meta.duration_seconds == 3.0


def test_mp4_mvhd_v1_truncated_gives_415_not_500():
    # mvhd v1 truncated to 25 bytes (less than required 32 bytes)
    data = make_mp4(duration_sec=3.0, mvhd_version=1, truncate_mvhd_bytes=87)
    with pytest.raises(AppError) as exc_info:
        validate_mp4_video_pure_python(data)
    assert exc_info.value.status_code == 415
    assert "Повреждён заголовок фильма" in exc_info.value.message


def test_valid_mp4_video_passes_pure_python():
    data = make_mp4(duration_sec=3.2, width=1080, height=1920)
    meta = validate_mp4_video_pure_python(data)
    assert meta.width == 1080
    assert meta.height == 1920
    assert meta.duration_seconds == 3.2
    assert meta.codec == "h264"
    assert meta.file_size == len(data)


def test_mp4_duration_over_5_seconds_rejected():
    data = make_mp4(duration_sec=5.05)  # 5.05 exceeds strict 5.0s limit
    with pytest.raises(AppError) as exc_info:
        validate_mp4_video_pure_python(data)
    assert exc_info.value.status_code == 422
    assert "превышает лимит 5 секунд" in exc_info.value.message


def test_mp4_duration_exactly_5_seconds_allowed():
    data = make_mp4(duration_sec=5.0)
    meta = validate_mp4_video_pure_python(data)
    assert meta.duration_seconds == 5.0


def test_mp4_with_audio_track_strictly_rejected():
    data = make_mp4(duration_sec=2.0, include_audio=True)
    with pytest.raises(AppError) as exc_info:
        validate_mp4_video_pure_python(data)
    assert exc_info.value.status_code == 422
    assert "звук запрещён" in exc_info.value.message


def test_mp4_wrong_codec_rejected():
    data = make_mp4(duration_sec=2.0, codec=b"hev1")  # H.265 instead of H.264
    with pytest.raises(AppError) as exc_info:
        validate_mp4_video_pure_python(data)
    assert exc_info.value.status_code == 422
    assert "Поддерживается только видеокодек H.264" in exc_info.value.message


def test_mp4_file_exceeding_15_mib_rejected():
    oversized = b"\x00" * (MAX_SPLASH_VIDEO_BYTES + 1)
    with pytest.raises(AppError) as exc_info:
        validate_mp4_video_pure_python(oversized)
    assert exc_info.value.status_code == 413
    assert "превышает максимальный лимит 15 МБ" in exc_info.value.message


def test_corrupt_or_truncated_file_rejected():
    with pytest.raises(AppError) as exc_info:
        validate_mp4_video_pure_python(b"not an mp4 file at all")
    assert exc_info.value.status_code in (415, 422)


def test_ffprobe_corrupt_video_rejected():
    # Valid ISO boxes from make_mp4 but corrupt H.264 bitstream
    data = make_mp4(duration_sec=2.0)
    with pytest.raises(AppError) as exc_info:
        validate_mp4_video_ffprobe(data)
    # ffprobe fails decoding or finding valid video stream -> 415 or 422
    assert exc_info.value.status_code in (415, 422)
