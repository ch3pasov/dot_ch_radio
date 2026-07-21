#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
temporary_root="${TMPDIR:-/tmp}"
test_config="$(mktemp -d "$temporary_root/dot-ch-radio-tests.XXXXXX")"

cleanup() {
  rm -rf -- "$test_config"
}
trap cleanup EXIT

for source in "$project_dir"/config_example/*.py; do
  cp -- "$source" "$test_config/"
done
cp -- "$project_dir/config/emoji_pack_links.json" "$test_config/"

docker build --tag dot-ch-radio:test "$project_dir"
docker run --rm \
  --user 0 \
  --mount "type=bind,src=$test_config,dst=/app/config,readonly" \
  --mount "type=bind,src=$project_dir/content/sf7-custom-emoji-index.json,dst=/app/content/sf7-custom-emoji-index.json,readonly" \
  --tmpfs /app/volume:rw,noexec,nosuid,mode=1777,size=16m \
  dot-ch-radio:test \
  python -m unittest discover -s tests -p 'test_*.py'
