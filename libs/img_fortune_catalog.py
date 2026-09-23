"""Read-only, prebuilt IMG video catalogue and offline collection helpers."""

import json
import re
from functools import lru_cache
from pathlib import Path


CATALOG_PATH = Path(__file__).resolve().parent.parent / "content" / "img-fortune-videos.json"
CODE_PATTERN = re.compile(r"[0-9]{4}")
VIDEO_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{11}")
TITLE_PATTERN = re.compile(
    r"IMG_([0-9]{4})(?:\.(?:MOV|MP4|M4V|AVI|3GP|3GPP|3G2|MPG|MPEG|MKV|WEBM|WMV|FLV|MTS|M2TS|TS))?",
    re.IGNORECASE,
)
DESCRIPTIVE_TITLE_PATTERN_TEMPLATE = r"(?<![A-Za-z0-9])IMG[_ ]{code}(?![A-Za-z0-9])"


def code_from_title(title: str) -> str | None:
    match = TITLE_PATTERN.fullmatch(title.strip())
    return match.group(1) if match else None


def title_contains_code(title: str, code: str) -> bool:
    """Allow a documented exception when YouTube adds context around IMG_####."""
    pattern = re.compile(
        DESCRIPTIVE_TITLE_PATTERN_TEMPLATE.format(code=re.escape(code)), re.IGNORECASE
    )
    return bool(pattern.search(title.strip()))


def search_candidates(html: str) -> list[dict]:
    """Extract exact IMG titles only, never recommendations with other names."""
    match = re.search(r"(?:var\s+)?ytInitialData\s*=\s*", html)
    if match is None:
        raise ValueError("YouTube search page contains no initial data")
    data = json.JSONDecoder().raw_decode(html[match.end():])[0]
    candidates = []

    def walk(value):
        if isinstance(value, dict):
            renderer = value.get("videoRenderer")
            if isinstance(renderer, dict):
                title_data = renderer.get("title", {})
                title = title_data.get("simpleText") or "".join(
                    run.get("text", "") for run in title_data.get("runs", [])
                )
                code = code_from_title(title)
                video_id = renderer.get("videoId", "")
                if code is not None and VIDEO_ID_PATTERN.fullmatch(video_id):
                    candidates.append({"code": code, "video_id": video_id, "title": title})
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    return candidates


def validate_catalog(catalog: dict, *, require_complete: bool = True) -> dict:
    if catalog.get("schema_version") != 1:
        raise ValueError("Unsupported IMG catalogue schema")
    videos = catalog.get("videos")
    if not isinstance(videos, dict):
        raise ValueError("IMG catalogue must contain a video mapping")
    if require_complete and set(videos) != {f"{number:04d}" for number in range(10000)}:
        raise ValueError("IMG catalogue must cover every code from 0000 to 9999")
    seen_ids = set()
    for code, video in videos.items():
        if not CODE_PATTERN.fullmatch(code) or not isinstance(video, dict):
            raise ValueError("Invalid IMG catalogue entry")
        video_id = video.get("video_id", "")
        if not VIDEO_ID_PATTERN.fullmatch(video_id) or video_id in seen_ids:
            raise ValueError(f"Invalid or duplicated video ID for IMG_{code}")
        title = video.get("title", "")
        if not isinstance(title, str):
            raise ValueError(f"Invalid video title for IMG_{code}")
        match_type = video.get("match_type", "exact")
        if match_type == "exact":
            if code_from_title(title) != code:
                raise ValueError(f"Video title does not match IMG_{code}")
        elif match_type == "descriptive_title":
            if not title_contains_code(title, code):
                raise ValueError(f"Exception video title does not contain IMG_{code}")
        else:
            raise ValueError(f"Unknown title match type for IMG_{code}")
        if not video.get("verified_at"):
            raise ValueError(f"Missing verification time for IMG_{code}")
        seen_ids.add(video_id)
    return videos


@lru_cache(maxsize=1)
def load_fortune_catalog() -> dict:
    with CATALOG_PATH.open(encoding="utf-8") as source:
        return validate_catalog(json.load(source))


def fortune_video_url(code: str) -> str:
    if not CODE_PATTERN.fullmatch(code):
        raise ValueError("Expected exactly four ASCII digits")
    return f"https://www.youtube.com/watch?v={load_fortune_catalog()[code]['video_id']}"


def fortune_video_entry(code: str) -> dict:
    if not CODE_PATTERN.fullmatch(code):
        raise ValueError("Expected exactly four ASCII digits")
    return load_fortune_catalog()[code]
