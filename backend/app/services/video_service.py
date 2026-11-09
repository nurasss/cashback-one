"""Video validation and metadata extraction service for mobile app splash screens.

Enforces:
- File size <= 15 MiB (15_728_640 bytes)
- MP4 container format
- H.264 video codec (avc1)
- Video duration <= 5.0 seconds
- Strictly NO audio tracks ("Видео без воспроизведения звука")
- Safe bounded ISO BMFF box parser (pure Python) + optional ffprobe secondary check.
"""
from __future__ import annotations

import io
import json
import logging
import os
import shutil
import struct
import subprocess
import tempfile
from dataclasses import dataclass

from app.core.errors import AppError

logger = logging.getLogger(__name__)

MAX_SPLASH_VIDEO_BYTES = 15 * 1024 * 1024  # 15 MiB
MAX_SPLASH_VIDEO_DURATION_SECONDS = 5.05  # 5 seconds with frame rounding tolerance


@dataclass(frozen=True)
class VideoMetadata:
    width: int
    height: int
    duration_seconds: float
    codec: str
    file_size: int


def _parse_iso_boxes(stream: io.BytesIO, end_pos: int, max_depth: int = 10) -> list[tuple[bytes, int, int]]:
    """Return list of (box_type, start_offset, box_size) in current container."""
    boxes: list[tuple[bytes, int, int]] = []
    if max_depth <= 0:
        return boxes

    while stream.tell() + 8 <= end_pos:
        start = stream.tell()
        header = stream.read(8)
        if len(header) < 8:
            break
        box_size, box_type = struct.unpack(">I4s", header)
        if box_size == 1:
            large_header = stream.read(8)
            if len(large_header) < 8:
                break
            box_size = struct.unpack(">Q", large_header)[0]
        elif box_size == 0:
            box_size = end_pos - start

        if box_size < 8 or start + box_size > end_pos:
            break

        boxes.append((box_type, start, box_size))
        stream.seek(start + box_size)

    return boxes


def validate_mp4_video_pure_python(data: bytes) -> VideoMetadata:
    """Pure Python ISO BMFF / MP4 parser validating codec, duration, dimensions, and audio tracks."""
    if len(data) > MAX_SPLASH_VIDEO_BYTES:
        raise AppError(
            "FILE_TOO_LARGE",
            f"Размер видео ({len(data)} байт) превышает максимальный лимит 15 МБ.",
            status_code=413,
        )

    if len(data) < 32:
        raise AppError(
            "UNSUPPORTED_MEDIA_TYPE",
            "Файл слишком мал для корректного MP4 видео.",
            status_code=415,
        )

    stream = io.BytesIO(data)
    file_len = len(data)
    top_boxes = _parse_iso_boxes(stream, file_len)

    top_types = [b[0] for b in top_boxes]
    if b"ftyp" not in top_types:
        raise AppError(
            "UNSUPPORTED_MEDIA_TYPE",
            "Некорректный формат файла: отсутствует заголовок MP4 (ftyp atom).",
            status_code=415,
        )

    moov_info = next((b for b in top_boxes if b[0] == b"moov"), None)
    if not moov_info:
        raise AppError(
            "UNSUPPORTED_MEDIA_TYPE",
            "Некорректная структура MP4: отсутствует секция метаданных (moov atom).",
            status_code=415,
        )

    _, moov_start, moov_size = moov_info
    moov_end = moov_start + moov_size
    stream.seek(moov_start + 8)
    moov_children = _parse_iso_boxes(stream, moov_end)

    # 1. Parse duration from mvhd
    mvhd_info = next((b for b in moov_children if b[0] == b"mvhd"), None)
    if not mvhd_info:
        raise AppError(
            "UNSUPPORTED_MEDIA_TYPE",
            "В структуре видео отсутствует заголовок фильма (mvhd).",
            status_code=415,
        )

    _, mvhd_start, mvhd_size = mvhd_info
    stream.seek(mvhd_start + 8)
    mvhd_data = stream.read(mvhd_size - 8)
    if len(mvhd_data) < 20:
        raise AppError(
            "UNSUPPORTED_MEDIA_TYPE",
            "Повреждён заголовок фильма (mvhd).",
            status_code=415,
        )

    version = mvhd_data[0]
    if version == 0:
        timescale, duration = struct.unpack(">II", mvhd_data[12:20])
    elif version == 1:
        timescale, duration = struct.unpack(">IQ", mvhd_data[20:32])
    else:
        raise AppError(
            "UNSUPPORTED_MEDIA_TYPE",
            f"Неподдерживаемая версия заголовка фильма ({version}).",
            status_code=415,
        )

    if timescale == 0:
        raise AppError(
            "UNSUPPORTED_MEDIA_TYPE",
            "Некорректная шкала времени видео (timescale=0).",
            status_code=415,
        )

    duration_seconds = round(duration / timescale, 2)
    if duration_seconds <= 0:
        raise AppError(
            "VALIDATION_ERROR",
            "Длительность видео должна быть больше 0 секунд.",
            status_code=422,
        )

    if duration_seconds > MAX_SPLASH_VIDEO_DURATION_SECONDS:
        raise AppError(
            "VALIDATION_ERROR",
            f"Длительность видео ({duration_seconds} с) превышает лимит 5 секунд.",
            status_code=422,
        )

    # 2. Iterate tracks: inspect video and strictly forbid audio (soun)
    video_found = False
    detected_codec = ""
    video_width = 0
    video_height = 0

    trak_boxes = [b for b in moov_children if b[0] == b"trak"]
    if not trak_boxes:
        raise AppError(
            "UNSUPPORTED_MEDIA_TYPE",
            "В видеофайле не найдено медиа-дорожек.",
            status_code=415,
        )

    for _, trak_start, trak_size in trak_boxes:
        trak_end = trak_start + trak_size
        stream.seek(trak_start + 8)
        trak_children = _parse_iso_boxes(stream, trak_end)

        # Parse tkhd for dimensions
        tkhd_info = next((b for b in trak_children if b[0] == b"tkhd"), None)
        trak_w = 0
        trak_h = 0
        if tkhd_info:
            _, tkhd_start, tkhd_size = tkhd_info
            stream.seek(tkhd_start + 8)
            tkhd_data = stream.read(tkhd_size - 8)
            tkhd_ver = tkhd_data[0] if tkhd_data else 0
            offset = 84 if tkhd_ver == 1 else 76
            if len(tkhd_data) >= offset + 8:
                raw_w, raw_h = struct.unpack(">II", tkhd_data[offset : offset + 8])
                trak_w = raw_w >> 16
                trak_h = raw_h >> 16

        # Parse mdia -> hdlr and minf -> stbl -> stsd
        mdia_info = next((b for b in trak_children if b[0] == b"mdia"), None)
        if not mdia_info:
            continue

        _, mdia_start, mdia_size = mdia_info
        stream.seek(mdia_start + 8)
        mdia_children = _parse_iso_boxes(stream, mdia_start + mdia_size)

        hdlr_info = next((b for b in mdia_children if b[0] == b"hdlr"), None)
        handler_type = b""
        if hdlr_info:
            _, hdlr_start, hdlr_size = hdlr_info
            stream.seek(hdlr_start + 8)
            hdlr_data = stream.read(hdlr_size - 8)
            if len(hdlr_data) >= 12:
                handler_type = hdlr_data[8:12]

        if handler_type == b"soun":
            raise AppError(
                "VALIDATION_ERROR",
                "Видео для заставки не должно содержать аудиодорожек (звук запрещён).",
                status_code=422,
            )

        if handler_type == b"vide":
            video_found = True
            video_width = max(video_width, trak_w)
            video_height = max(video_height, trak_h)

            minf_info = next((b for b in mdia_children if b[0] == b"minf"), None)
            if minf_info:
                _, minf_start, minf_size = minf_info
                stream.seek(minf_start + 8)
                minf_children = _parse_iso_boxes(stream, minf_start + minf_size)
                stbl_info = next((b for b in minf_children if b[0] == b"stbl"), None)
                if stbl_info:
                    _, stbl_start, stbl_size = stbl_info
                    stream.seek(stbl_start + 8)
                    stbl_children = _parse_iso_boxes(stream, stbl_start + stbl_size)
                    stsd_info = next((b for b in stbl_children if b[0] == b"stsd"), None)
                    if stsd_info:
                        _, stsd_start, stsd_size = stsd_info
                        stream.seek(stsd_start + 8)
                        stsd_data = stream.read(stsd_size - 8)
                        # stsd header: version (1) + flags (3) + entry_count (4)
                        if len(stsd_data) >= 16:
                            # sample entry starts at offset 8: size (4) + format (4)
                            sample_format = stsd_data[12:16].decode("ascii", errors="replace").strip()
                            detected_codec = sample_format

    if not video_found:
        raise AppError(
            "UNSUPPORTED_MEDIA_TYPE",
            "В файле не найдено видеодорожки.",
            status_code=415,
        )

    # Valid H.264 formats: avc1, avc3
    if detected_codec not in ("avc1", "avc3", "h264"):
        raise AppError(
            "VALIDATION_ERROR",
            f"Поддерживается только видеокодек H.264 (обнаружен: {detected_codec or 'неизвестен'}).",
            status_code=422,
        )

    return VideoMetadata(
        width=video_width,
        height=video_height,
        duration_seconds=duration_seconds,
        codec="h264",
        file_size=len(data),
    )


def validate_mp4_video_ffprobe(data: bytes) -> VideoMetadata | None:
    """Secondary probe using ffprobe binary if available in system PATH."""
    ffprobe_path = shutil.which("ffprobe")
    if not ffprobe_path:
        return None

    # Write to a secure temporary file
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        cmd = [
            ffprobe_path,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            tmp_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3.0, check=False)
        if res.returncode != 0:
            logger.warning("ffprobe check returned %d: %s", res.returncode, res.stderr)
            return None

        probe_info = json.loads(res.stdout)
        streams = probe_info.get("streams", [])
        # Check audio
        for s in streams:
            if s.get("codec_type") == "audio":
                raise AppError(
                    "VALIDATION_ERROR",
                    "Видео для заставки не должно содержать аудиодорожек (звук запрещён).",
                    status_code=422,
                )

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        if not video_stream:
            raise AppError(
                "UNSUPPORTED_MEDIA_TYPE",
                "В файле не найдено видеодорожки.",
                status_code=415,
            )

        codec_name = video_stream.get("codec_name", "").lower()
        if codec_name != "h264":
            raise AppError(
                "VALIDATION_ERROR",
                f"Поддерживается только видеокодек H.264 (обнаружен: {codec_name}).",
                status_code=422,
            )

        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))

        # Duration
        format_info = probe_info.get("format", {})
        dur_str = format_info.get("duration") or video_stream.get("duration") or "0"
        duration_seconds = round(float(dur_str), 2)

        if duration_seconds > MAX_SPLASH_VIDEO_DURATION_SECONDS:
            raise AppError(
                "VALIDATION_ERROR",
                f"Длительность видео ({duration_seconds} с) превышает лимит 5 секунд.",
                status_code=422,
            )

        return VideoMetadata(
            width=width,
            height=height,
            duration_seconds=duration_seconds,
            codec="h264",
            file_size=len(data),
        )
    except subprocess.TimeoutExpired:
        logger.warning("ffprobe probe timed out")
        return None
    except json.JSONDecodeError:
        return None
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def validate_mp4_video(data: bytes) -> VideoMetadata:
    """Validate MP4 video with pure Python parser and optional ffprobe confirmation."""
    # Always run the pure Python parser first (strict bounds, no external execution)
    meta = validate_mp4_video_pure_python(data)

    # If ffprobe is present, verify consistency
    try:
        ffprobe_meta = validate_mp4_video_ffprobe(data)
        if ffprobe_meta and ffprobe_meta.width > 0 and meta.width == 0:
            return ffprobe_meta
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.debug("Optional ffprobe check skipped: %s", exc)

    return meta
