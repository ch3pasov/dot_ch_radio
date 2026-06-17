import asyncio
import json
import mimetypes
import re
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from global_vars import app_robot, loop, print
from volume.config.tg_ids import admins

ROOT = Path(__file__).resolve().parent.parent
CONTENT_PATH = ROOT / "volume" / "content.py"
ASSET_INDEX_PATH = ROOT / "volume" / "telegram_assets.json"
ASSET_ARCHIVE_CHAT_ID = admins[0]
BUCKET_URL_RE = re.compile(r"https://storage\.yandexcloud\.net/dot-ch-bot-bucket/[^)\]\"\s]+")


def content_urls():
    text = CONTENT_PATH.read_text(encoding="utf-8")
    return sorted(set(BUCKET_URL_RE.findall(text)))


def asset_name(url):
    parsed = urllib.parse.urlparse(url)
    return Path(urllib.parse.unquote(parsed.path)).name


def download(url, target_dir):
    name = asset_name(url)
    suffix = Path(name).suffix
    target = Path(target_dir) / name
    quoted_url = urllib.parse.urlsplit(url)
    safe_path = urllib.parse.quote(urllib.parse.unquote(quoted_url.path), safe="/%")
    safe_url = urllib.parse.urlunsplit((quoted_url.scheme, quoted_url.netloc, safe_path, quoted_url.query, quoted_url.fragment))
    with urllib.request.urlopen(safe_url, timeout=60) as response:
        target.write_bytes(response.read())
        content_type = response.headers.get("content-type") or mimetypes.guess_type(name)[0]
    if suffix and not target.name.endswith(suffix):
        target = target.with_suffix(suffix)
    return target, content_type


def load_index():
    if not ASSET_INDEX_PATH.exists():
        return {"generated_at": None, "assets": {}}
    return json.loads(ASSET_INDEX_PATH.read_text(encoding="utf-8"))


def media_kind(message):
    media = getattr(message, "media", None)
    if media is None:
        return None
    if getattr(media, "photo", None) is not None:
        return "photo"
    if getattr(media, "document", None) is not None:
        return "document"
    return type(media).__name__


async def upload_assets():
    index = load_index()
    assets = index.setdefault("assets", {})
    urls = content_urls()

    await app_robot.start()
    with tempfile.TemporaryDirectory() as tmpdir:
        for position, url in enumerate(urls, start=1):
            if url in assets and assets[url].get("message_id"):
                print(f"[{position}/{len(urls)}] skip {asset_name(url)}")
                continue

            local_path, content_type = download(url, tmpdir)
            caption = f"dot_ch_radio asset backup\n{asset_name(url)}\n{url}"
            print(f"[{position}/{len(urls)}] upload {local_path.name}")
            message = await app_robot.send_file(ASSET_ARCHIVE_CHAT_ID, local_path, caption=caption)
            assets[url] = {
                "chat_id": ASSET_ARCHIVE_CHAT_ID,
                "message_id": message.id,
                "file_name": local_path.name,
                "content_type": content_type,
                "media_kind": media_kind(message),
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
            }

    index["generated_at"] = datetime.now(timezone.utc).isoformat()
    index["source"] = str(CONTENT_PATH)
    index["assets_count"] = len(assets)
    ASSET_INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {ASSET_INDEX_PATH} with {len(assets)} assets")


if __name__ == "__main__":
    loop.run_until_complete(upload_assets())
