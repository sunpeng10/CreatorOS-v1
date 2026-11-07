import re
import subprocess
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

TEXT_SUFFIXES = {'.txt', '.md', '.srt', '.vtt'}
IMAGE_SUFFIXES = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP'}


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def parse_media(path: Path, suffix: str, max_seconds: int):
    if suffix in TEXT_SUFFIXES:
        raw = path.read_bytes()
        if b'\x00' in raw or raw.startswith(b'MZ'):
            raise HTTPException(422, '文件不是有效 UTF-8 文本')
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise HTTPException(422, '请将文本转换为 UTF-8 编码')
        if len(text) > 200000:
            raise HTTPException(413, '文本最多 200000 字符')
        return {'kind': 'subtitle' if suffix in {'.srt', '.vtt'} else 'text', 'text': text, 'characters': len(text), 'paragraphs': len([p for p in text.splitlines() if p.strip()])}
    if suffix in IMAGE_SUFFIXES:
        try:
            with Image.open(path) as im:
                if im.format != IMAGE_SUFFIXES[suffix] or im.width * im.height > 40000000:
                    raise ValueError('图像格式不符或超过 4000 万像素')
                width, height = im.size
                im.verify()
            return {'kind': 'image', 'width': width, 'height': height}
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise HTTPException(422, '图片损坏、格式不符或像素过大')
    if suffix not in {'.mp4', '.mov'}:
        raise HTTPException(422, '仅支持 MP4/MOV、JPG/PNG/WebP、TXT/Markdown/SRT/VTT')
    with path.open('rb') as file:
        signature = file.read(32)
    if len(signature) < 12 or signature[4:8] not in {b'ftyp', b'moov', b'wide', b'mdat'}:
        raise HTTPException(422, '视频文件签名无效')
    try:
        import cv2
        cap = cv2.VideoCapture(str(path))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        ok, _ = cap.read()
        cap.release()
        duration = count / fps if fps > 0 else 0
        if not ok or duration <= 0 or width <= 0 or height <= 0:
            raise HTTPException(422, '视频无法解码或已损坏')
        if duration > max_seconds or width * height > 3840 * 2160:
            raise HTTPException(413, f'视频最多 {max_seconds} 秒且不超过 4K，请裁剪或压缩')
        # FFmpeg's demuxer is restricted to local file/pipe protocols.
        probe = subprocess.run([ffmpeg_exe(), '-protocol_whitelist', 'file,pipe', '-i', str(path), '-t', '1', '-f', 'null', '-'], capture_output=True, timeout=20)
        if probe.returncode != 0:
            raise HTTPException(422, 'FFmpeg 无法解析该视频')
        return {'kind': 'video', 'duration': round(duration, 3), 'fps': round(fps, 3), 'width': width, 'height': height, 'has_audio': bool(re.search(rb'Audio:', probe.stderr)), 'transcription': '未自动转录；可上传字幕 SRT/VTT 或文稿', 'decoder': 'FFmpeg + OpenCV'}
    except (subprocess.TimeoutExpired, OSError):
        raise HTTPException(422, '媒体解析超时或解码器不可用')


def video_frames(path: Path, metadata: dict):
    import cv2
    from scenedetect import ContentDetector, SceneManager, open_video
    duration = metadata['duration']
    warning = ''
    try:
        video = open_video(str(path))
        manager = SceneManager()
        manager.add_detector(ContentDetector(threshold=30))
        manager.auto_downscale = False
        manager.downscale = max(1, metadata['width'] // 320)
        manager.detect_scenes(video=video, frame_skip=max(0, int(metadata['fps'] / 3) - 1))
        scenes = [{'start': round(start.get_seconds(), 2), 'end': round(end.get_seconds(), 2)} for start, end in manager.get_scene_list(start_in_scene=True)][:60]
    except Exception:
        scenes = [{'start': 0.0, 'end': duration}]
        warning = '切镜头检测不可用，展示全片时间区间与均匀抽帧'
    if not scenes:
        scenes = [{'start': 0.0, 'end': duration}]
    positions = sorted(set([0.0, round(duration / 2, 2)] + [scene['start'] for scene in scenes]))[:8]
    frames = []
    cap = cv2.VideoCapture(str(path))
    try:
        for idx, position in enumerate(positions):
            cap.set(cv2.CAP_PROP_POS_MSEC, position * 1000)
            ok, frame = cap.read()
            if not ok:
                continue
            frame = cv2.resize(frame, (640, max(1, int(frame.shape[0] * 640 / frame.shape[1]))))
            target = path.with_name(path.stem + f'-frame-{idx}.jpg')
            success, encoded = cv2.imencode('.jpg', frame)
            if success:
                target.write_bytes(encoded.tobytes())
                frames.append({'path': str(target), 'timecode': position})
    finally:
        cap.release()
    return scenes, frames, warning
