#!/usr/bin/env python3
"""Offline collector. Keep checkpoints outside the live content mount.

Only a complete, title-verified catalogue is written to --output. No YouTube
credentials, user data, downloads or application runtime state are involved.
"""

import argparse
import concurrent.futures
import gzip
import http.client
import json
import random
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from libs.img_fortune_catalog import code_from_title, search_candidates, validate_catalog


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RateLimitedClient:
    def __init__(self, requests_per_second):
        self.interval = 1 / requests_per_second
        self.next_request = 0
        self.lock = threading.Lock()

    def get(self, url):
        for attempt in range(4):
            with self.lock:
                wait = max(0, self.next_request - time.monotonic())
                self.next_request = max(time.monotonic(), self.next_request) + self.interval
            time.sleep(wait)
            request = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; dot-ch-radio-catalog/1.0)",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip",
            })
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    body = response.read()
                    if response.headers.get("Content-Encoding") == "gzip":
                        body = gzip.decompress(body)
                    return body.decode("utf-8")
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    retry_after = exc.headers.get("Retry-After", "60")
                    cooldown = max(60, int(retry_after) if retry_after.isdigit() else 60)
                    with self.lock:
                        self.next_request = max(self.next_request, time.monotonic() + cooldown)
                    if attempt == 3:
                        raise RuntimeError("YouTube rate limit persisted; resume the checkpoint later") from exc
                elif exc.code in (500, 502, 503, 504) and attempt < 3:
                    time.sleep(2 ** attempt)
                else:
                    raise
            except (
                TimeoutError,
                urllib.error.URLError,
                http.client.IncompleteRead,
                http.client.RemoteDisconnected,
                ConnectionResetError,
            ):
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError("Request retries exhausted")


def save_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def collect(args):
    checkpoint = Path(args.checkpoint)
    state = json.loads(checkpoint.read_text()) if checkpoint.exists() else {
        "schema_version": 1, "videos": {}, "candidates": {}, "searched": [], "rejected": [],
    }
    videos = validate_catalog(state, require_complete=False)
    candidates = state.setdefault("candidates", {})
    searched = set(state.setdefault("searched", []))
    rejected = set(state.setdefault("rejected", []))
    client = RateLimitedClient(args.requests_per_second)
    codes = [f"{number:04d}" for number in range(args.start, args.stop)]
    random.Random(0).shuffle(codes)
    # Start with the user's example and a few boundaries for immediate feedback.
    codes.sort(key=lambda code: code not in {"0000", "6789", "9999", "2109", "2902"})
    started = time.monotonic()
    last_report = 0
    search_count = 0
    fallback_searches = 0
    verify_count = 0
    errors = 0
    deadline = datetime.fromisoformat(args.deadline).timestamp() if args.deadline else float("inf")
    if args.retry_missing:
        searched.difference_update(
            f"{number:04d}" for number in range(args.start, args.stop)
            if f"{number:04d}" not in videos
        )

    single_queries = set()

    def search(batch):
        quoted = " OR ".join(f'"IMG_{code}"' for code in batch)
        plain = " OR ".join(f"IMG_{code}" for code in batch)
        region = {"gl": args.region_code} if args.region_code else {}
        for attempt in range(3):
            query = urllib.parse.urlencode({"search_query": quoted, "hl": "en", **region})
            html = client.get("https://www.youtube.com/results?" + query)
            try:
                found = search_candidates(html)
                if not {item["code"] for item in found}.intersection(batch):
                    fallback_query = urllib.parse.urlencode({"search_query": plain, "hl": "en", **region})
                    fallback_html = client.get("https://www.youtube.com/results?" + fallback_query)
                    return search_candidates(fallback_html), True
                return found, False
            except ValueError:
                if attempt == 2:
                    raise
                time.sleep(1 + attempt)

    def verify(code, candidate):
        url = "https://www.youtube.com/oembed?" + urllib.parse.urlencode({
            "url": f"https://www.youtube.com/watch?v={candidate['video_id']}", "format": "json",
        })
        try:
            data = json.loads(client.get(url))
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 401, 403, 404, 410):
                return None
            raise
        if data.get("type") != "video" or code_from_title(data.get("title", "")) != code:
            return None
        return {"video_id": candidate["video_id"], "title": data["title"], "verified_at": utc_now(), "verified_via": "youtube_oembed"}

    def save_progress():
        state["searched"] = sorted(searched)
        state["rejected"] = sorted(rejected)
        save_json(checkpoint, state)
        missing = sum(code not in videos for code in codes)
        print(f"verified={len(videos)}/10000 missing_in_range={missing} "
              f"searches={search_count} fallback={fallback_searches} checks={verify_count} errors={errors} "
              f"elapsed={time.monotonic() - started:.0f}s", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {}
        active_codes = set()
        while True:
            if time.time() >= deadline - 45:
                print("Deadline reached; saving progress and finishing active requests.", flush=True)
                break
            for code in codes:
                if len(pending) >= args.workers:
                    break
                if code in videos or code in active_codes:
                    continue
                options = [item for item in candidates.get(code, []) if item["video_id"] not in rejected]
                if options:
                    candidate = options[0]
                    future = pool.submit(verify, code, candidate)
                    pending[future] = ("verify", [code], candidate["video_id"])
                    active_codes.add(code)
                elif code not in searched:
                    batch = [code]
                    if code not in single_queries:
                        for other in codes:
                            if len(batch) >= args.search_batch_size:
                                break
                            if other != code and other not in videos and other not in active_codes and other not in searched and other not in single_queries:
                                batch.append(other)
                    future = pool.submit(search, batch)
                    pending[future] = ("search", batch, None)
                    active_codes.update(batch)
                else:
                    continue
            if not pending:
                break
            done, _ = concurrent.futures.wait(pending, timeout=10, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                kind, batch, video_id = pending.pop(future)
                code = batch[0]
                active_codes.difference_update(batch)
                try:
                    result = future.result()
                except Exception as exc:
                    errors += 1
                    print(f"{kind} IMG_{code}: {type(exc).__name__}: {exc}", flush=True)
                    save_progress()
                    # Stop on upstream transport/markup failures, preserving all
                    # successful work. Don't mislabel an outage as missing videos.
                    raise
                if kind == "search":
                    search_count += 1
                    result, used_fallback = result
                    fallback_searches += int(used_fallback)
                    searched.update(batch)
                    if len(batch) > 1:
                        found_codes = {item["code"] for item in result}
                        for missing_code in set(batch) - found_codes:
                            searched.discard(missing_code)
                            single_queries.add(missing_code)
                    for item in result:
                        bucket = candidates.setdefault(item["code"], [])
                        if item["video_id"] not in {previous["video_id"] for previous in bucket}:
                            bucket.append(item)
                        if args.verification == "search" and item["code"] not in videos:
                            videos[item["code"]] = {
                                "video_id": item["video_id"], "title": item["title"],
                                "verified_at": utc_now(), "verified_via": "youtube_search",
                            }
                else:
                    verify_count += 1
                    if result is None:
                        rejected.add(video_id)
                    else:
                        videos[code] = result
            if time.monotonic() - last_report >= 20:
                save_progress()
                last_report = time.monotonic()
    save_progress()
    missing = [code for code in codes if code not in videos]
    print(f"Missing codes ({len(missing)}): " + ", ".join(missing[:50]), flush=True)
    if len(videos) == 10000:
        catalog = {
            "schema_version": 1,
            "generated_at": utc_now(),
            "source": "YouTube search; entries are exact IMG titles or explicitly marked descriptive-title matches. Verification method is recorded per entry.",
            "videos": dict(sorted(videos.items())),
        }
        validate_catalog(catalog)
        save_json(Path(args.output), catalog)
        print(f"Complete catalogue written to {args.output}", flush=True)
    return 1 if missing else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int, default=10000)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--requests-per-second", type=float, default=8)
    parser.add_argument("--verification", choices=("search", "oembed"), default="oembed")
    parser.add_argument("--deadline", help="Stop by this ISO 8601 time, including UTC offset")
    parser.add_argument("--search-batch-size", type=int, choices=(1, 2), default=1)
    parser.add_argument("--retry-missing", action="store_true", help="Repeat searches for codes missing from the checkpoint")
    parser.add_argument("--region-code", choices=("US", "GB", "RS", "DE", "RU", "CA", "AU", "IN", "JP", "FR", "ES", "IT", "BR"), help="Bias YouTube search to a country")
    args = parser.parse_args()
    if not 0 <= args.start < args.stop <= 10000 or not 1 <= args.workers <= 16 or not 0 < args.requests_per_second <= 10:
        parser.error("Invalid range or concurrency (at most 16 workers and 10 requests/second)")
    raise SystemExit(collect(args))
