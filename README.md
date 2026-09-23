# dot_ch_radio

A live Telegram radio and stateless toolbox built for
[@ch_an](https://t.me/ch_an). [@dot_ch_bot](https://t.me/dot_ch_bot) renders the
interactive menu and tools; a second Telethon account streams selected radio
stations into the channel's group call.

[Open the bot](https://t.me/dot_ch_bot) ·
[Open the channel](https://t.me/ch_an) ·
[Privacy model](PRIVACY.md)

<a href="https://t.me/ch_an/2105"><img src="docs/assets/circle-inversion.jpg" width="560" alt="A self-portrait after geometric circle inversion"></a>

## What it does

- keeps a Telegram group-call radio running, switches stations from the bot,
  restores interrupted streams and follows a separate day/night schedule;
- renders a declarative content tree with stable deep links, Telegram button
  styles, custom emoji icons and stateless navigation;
- renders that tree and all interactive responses in Russian or English from
  each sender's current Telegram interface language, with English as fallback;
- performs geometric circle inversion on photographs and Telegram video notes;
- searches the project's SF Symbols 7 custom-emoji catalogue;
- turns a date or four digits into a direct `IMG_XXXX` home-video link;
- provides small channel tools: weather, text generators, games and a
  deliberately empty application-side data takeout.

The bot has no application database, user profiles, request history or
analytics store. Telegram sessions are reduced to authentication data and
update cursors; user media is processed in memory. The exact boundary is
documented in [PRIVACY.md](PRIVACY.md).

## Circle inversion

The inversion is the actual geometric transform with respect to a circle, not
a colour negative.

- In a private chat, send the bot a photograph or a video note directly.
- In a group, reply to a photograph or video note with a message beginning
  with `@dot_ch_bot`.

Photographs are transformed with Pillow and NumPy. Video notes use NumPy to
build FFmpeg `remap` coordinate maps, preserve the audio track and run outside
Telegram's event loop. Input, maps and output are passed to FFmpeg through
anonymous memory-backed file descriptors. If Telegram privacy settings reject
the round message, the bot sends the result as a regular video with a link to
the relevant setting.

Video-note support was proposed by
[@enovikov11](https://github.com/enovikov11) in
[PR #1](https://github.com/ch3pasov/dot_ch_radio/pull/1). The current Telethon
implementation is independent and does not require OpenCV or a native
extension.

## Date divination

Open **Tools and generators → Date divination**, or use the
[direct link](https://t.me/dot_ch_bot?start=img_fortune). Choose a month and day
using the buttons, or send `/fortune 21.09`. In a private chat, a standalone
`21.09` also works. An optional year (`21.09.1990`) is validated but does not
affect the search; February 29 is accepted when no year is provided.

The date becomes `IMG_2109`. YouTube titles can use the bare filename or a
common video extension such as `.MOV`, `.MP4` or `.AVI`. Any four ASCII digits also work, including
`/fortune 6789`, `/fortune 0000` and `/fortune 9999`. The bot returns a direct
YouTube video link with a preview, using a static catalogue rather than a live
search. Dates and navigation state are not stored. In groups, use
`/fortune 6789` or `/fortune@dot_ch_bot 21.09`; ordinary dates are ignored.

The deployment requires `content/img-fortune-videos.json` with exactly 10,000
entries. Startup rejects missing or incomplete catalogues. Each entry records
the actual video title, ID, verification time and verification source. Nearly
all titles match `IMG_XXXX` exactly (case-insensitive), with an optional known
video extension. A small, marked exception set allows descriptive YouTube
titles when the same `IMG_XXXX` filename appears in the title; the bot shows
that full title with the link. Image extensions and unrelated recommendations
are excluded. YouTube search verification confirms the indexed title and
link; oEmbed verification additionally confirms public embed metadata. Neither
guarantees that a video will remain available later.

The offline collector is resumable and never runs inside the bot. Keep its
checkpoint and draft output outside the live content directory:

```bash
python3 scripts/build_img_fortune_catalog.py \
  --checkpoint /tmp/img-fortune-catalog-progress.json \
  --output /tmp/img-fortune-videos.json \
  --verification search --search-batch-size 2
```

It only writes the output once all 10,000 codes are covered. Review and copy that
file into `content/`, then rebuild and recreate the service. Use
`--verification oembed` to verify newly collected candidates through oEmbed.
A saved checkpoint keeps the verification source and any explicitly marked
descriptive-title exceptions for entries already collected.

## Runtime layout

The production process contains two Telethon clients:

- `robot_account` handles the bot UI, callbacks and tools;
- `dj_account` joins the group call and feeds it through PyTgCalls.

Both clients use the same event loop. The content tree is normalized and
validated on startup; its schema is described in
[content/CONTENT_SCHEMA.md](content/CONTENT_SCHEMA.md).

Language selection is stateless. A Russian Telegram interface receives the
Russian UI; every other or missing language code receives English. Changing
Telegram's interface language and reopening the menu is enough—there is no
per-user language setting in the bot.

## Run it

This is a personal production bot rather than a turnkey template: you need a
Telegram app, an existing channel/group call and two authorized Telethon
sessions.

1. Copy the Python config examples without overwriting the tracked emoji-pack
   index:

   ```bash
   cp config_example/*.py config/
   ```

2. Fill the channel IDs and local settings in `config/`. Copy `.env.example`
   to `.env` and provide `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`.
   `OPENWEATHER_API_KEY` is optional unless the weather tool is enabled.
3. Put the authorized SQLite sessions at
   `volume/sessions/robot_account.session` and
   `volume/sessions/dj_account.session`. Session files must never be committed.
4. Optionally provide `config/night_loop.mp4` for the scheduled night stream.
5. Start the service:

   ```bash
   docker compose up -d --build
   ```

`compose-with-secrets` is the owner's deployment wrapper for injecting the
same environment variables from a scoped 1Password vault. Plain Docker Compose
works with exported variables or a local `.env` file.

To verify existing sessions without starting handlers or joining the voice
chat:

```bash
docker compose run --rm dot_ch_radio python scripts/check_login.py
```

## Tests

The test runner builds the same Docker image, mounts placeholder config and the
generated emoji index read-only, and runs the complete `unittest` suite:

```bash
./scripts/run_tests.sh
```

## License

Copyright © 2023–2026 Anatolii Chepasov.

The project is licensed under the
[GNU Affero General Public License v3.0 only](LICENSE). If you modify the bot
and make that version available to users over a network, you must offer those
users its corresponding source code under the same license. Dependencies keep
their own licenses.
