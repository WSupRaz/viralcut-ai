from pathlib import Path

from scenedetect import ContentDetector, detect


def detect_scenes(video_path: Path) -> list[dict]:
    """Content-aware cut detection (ADR-0003) on the low-res proxy -- runs
    on CPU, no GPU, and the proxy's resolution is more than enough for
    detecting hard cuts."""
    scene_list = detect(str(video_path), ContentDetector())
    return [
        {"start": start.get_seconds(), "end": end.get_seconds()} for start, end in scene_list
    ]
