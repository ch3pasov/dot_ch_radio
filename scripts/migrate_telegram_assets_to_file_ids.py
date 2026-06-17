import asyncio
import json
import tempfile
from pathlib import Path

from telethon import utils

from global_vars import app_robot, loop, print

ROOT = Path(__file__).resolve().parent.parent
ASSET_INDEX_PATH = ROOT / "volume" / "telegram_assets.json"


async def migrate_assets():
    index = json.loads(ASSET_INDEX_PATH.read_text(encoding="utf-8"))
    assets = index.get("assets", {})

    await app_robot.start()
    migrated = 0
    skipped = 0
    for url, asset in assets.items():
        if asset.get("file_id"):
            skipped += 1
            continue

        message = await app_robot.get_messages(int(asset["chat_id"]), ids=int(asset["message_id"]))
        media = getattr(message, "media", None)
        file_id = None
        try:
            file_id = utils.pack_bot_file_id(media)
        except AttributeError as exc:
            print(f"reupload as document {asset.get('file_name')}: {exc}")

        if not file_id:
            with tempfile.TemporaryDirectory() as tmpdir:
                local_path = await app_robot.download_media(message, file=tmpdir)
                document_message = await app_robot.send_file(
                    int(asset["chat_id"]),
                    local_path,
                    force_document=True,
                    caption=f"dot_ch_radio file_id document copy\n{asset.get('file_name')}",
                )
            asset["legacy_chat_id"] = asset["chat_id"]
            asset["legacy_message_id"] = asset["message_id"]
            asset["chat_id"] = int(asset["chat_id"])
            asset["message_id"] = document_message.id
            asset["media_kind"] = "document"
            media = getattr(document_message, "media", None)
            file_id = utils.pack_bot_file_id(media)

        if not file_id:
            raise RuntimeError(f"Could not pack file_id for {asset.get('file_name')} ({url})")

        asset["file_id"] = file_id
        migrated += 1
        print(f"file_id {asset.get('file_name')}")

    index["file_ids_count"] = sum(1 for asset in assets.values() if asset.get("file_id"))
    ASSET_INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"migrated={migrated} skipped={skipped} file_ids={index['file_ids_count']}")


if __name__ == "__main__":
    loop.run_until_complete(migrate_assets())
