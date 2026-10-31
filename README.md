# KÖLJA TV (tv.kolja.com.br)

The site and the programme schedule (grade) of **KÖLJA TV**, channel 1 of the Retrotv app. Meant to live as the
public repo `koljatv/koljatv.github.io` (organisation `koljatv`), so it's served at https://tv.kolja.com.br/ (custom domain; https://koljatv.github.io/ redirects there).
The app only shows what this repo publishes; everything that decides what's on the air lives here, so a dead link
or a title that has to go is fixed by editing a JSON file, never by a new APK. Public: display material and code
only, never secrets, keys or personal data.

## What gets published (GitHub Pages)

| path | what it is |
|---|---|
| `/` | `public/index.html`: what's on now, the next 24 hours, about. Reads the two files below. |
| `/grade/schedule2.json` | the next 3 days, item by item: `[start, end, id, block(, part)]` (ms since 1970, UTC), every title on the air with its copies in order (and, for features, where each copy breaks), our pieces, the blocks' names. `rev` names this build. Format 2, with the commercial breaks: what Retrotv 0.3.1+ plays. |
| `/grade/schedule.json` | the same shelves laid out without breaks, format 1 (`[start, end, id, block]`), for Retrotv 0.3.0 sets. |
| `/legendas/` | our own subtitles: `<id>.pt-BR.vtt` and `<id>.en.vtt` (WebVTT), and `index.json`, which lists the subtitled titles, their languages, a revision tag and, per copy (a hash of its address), how that copy's clock lines up with the subtitles. See "Subtitles" below. |
| `/grade/now.json` | what's on now (with the offset into it), the next 8 items, the stand-ins in force, and the current `rev`. Rebuilt every run, not kept in git. |

Our own vignettes, idents, "apresenta", station card and break bumpers are **Release assets** (tag
`ours-v1`, see `catalog/grade.json` › `ours_base`), not in git: `media/ours/` locally, uploaded with
`tools/release_ours.sh`.

The app reads `now.json` when the channel comes on and every 10 minutes, and fetches `schedule2.json` (0.3.0:
`schedule.json`) only when its `rev` changed (`rev2` / `rev`). It keeps the last good copy, so it still plays if GitHub is unreachable for a while (the file
covers 3 days). Our pieces are fetched once and kept on the phone. When a film fails mid-play it shows
"PROBLEMAS TÉCNICOS · JÁ VOLTAMOS", re-reads `now.json` and goes where the schedule says.

## How it runs

`.github/workflows/grade.yml`, every 20 minutes (and on every push to `catalog/` or `tools/`):

1. `tools/check.py` sends a 64 KB ranged GET to every copy of every title airing in the next 8 hours, plus 60
   more titles a run (the ones checked longest ago), so the whole shelf is seen about four times a day. A copy
   is bad after two failures in a row and good again on its first answer. The results (`state/health.json`) live
   in the Actions cache, not in git.
2. `tools/build.py` lays out the days (the same layout every time for the same date and catalogue). Each block
   plays its shelf like a tape, wound day by day from `grade.json` › `epoch`: every title airs once before the
   first rerun and none is skipped (a title that doesn't fit the end of a slot opens the block's next one; one of
   the next few that does fit may air early, and its turn is then passed over). Series and serials keep their
   episode order and take turns, like a matinee running several serials. Shorts of the other blocks fill what's
   left of a slot, from a tape of their own, never twice a day. `python3 tools/rotation.py` says how many days go
   by before the first rerun, block by block (31 Oct 2026, with the dayparts: 10 days, 1,148 titles, 558 hours; the cartoons, 7½ hours a day, 9). It puts the healthy copies of
   each title first and, where none of a title's copies answers, puts a playable title of the same block that fits
   the slot (the longest first) in its place, with the station card for the remainder.
3. When `grade/schedule2.json` or `grade/schedule.json` changed, they're committed (`grade: <rev>`); `public/` is then deployed to Pages.

Live since 31 October 2026: organisation `koljatv` (free plan, owned by Niko's account), public repo
`koljatv/koljatv.github.io`, Settings › Pages › Source: **GitHub Actions**, release `ours-v1` with our pieces. A
public repo gets Pages and unlimited Actions minutes on the free plan (private would burn ~2,200 of the 2,000 free
minutes a month at one ~1-minute run every 20 minutes). Scheduled workflows stop after 60 days without repo
activity; the daily schedule commit keeps it alive.

## Publishing changes

This folder is a clone with `origin` = `koljatv/koljatv.github.io` and pushes as Niko's GitHub account (`gh`,
logged in). Whoever works here (Niko, or one of us through the chat) publishes like this:

1. Commit with this repo's own identity (already set in `.git/config`: `KÖLJA TV` + GitHub noreply address), never
   a personal e-mail.
2. `git pull --rebase` first: the workflow commits `grade: <rev>` to `main` on its own whenever the schedule changes.
3. `git push`. A push touching `catalog/`, `tools/`, `public/index.html` or the workflow rebuilds and redeploys in
   a minute or two (`gh run list -R koljatv/koljatv.github.io`); then check `https://tv.kolja.com.br/grade/now.json`.
4. New or changed pieces in `media/ours/`: `tools/release_ours.sh --clobber` (new names also go in `grade.json` ›
   `ours`).

The commercial breaks live in their own file so no phone is left behind: Retrotv 0.3.0 reads format 1 only and
keeps fetching `schedule.json` (the shelves laid out without breaks, exactly as before), while 0.3.1 reads
`schedule2.json` (format 2, with the breaks) because `now.json` names it (`schedule2`, `rev2`). Keep writing both
as long as 0.3.0 sets are around. Only `main` is published; never push other branches.

## Commercial breaks

Features (films of 40 minutes or more) go to a break about every 25 minutes; shorts, cartoons and episodes play
straight. `python3 tools/breaks.py` finds the places: around each even split point it has ffmpeg watch a few
minutes of the copy (ranged reads, nothing kept) and picks the end of a fade to black, else a scene cut in a
pause of the soundtrack (away from dialogue), else the strongest cut. Every copy is measured on its own and the
result is kept in `catalog/breaks.json`, keyed by URL (a copy not measured yet gets the measured copy's places
scaled to its length; a title with none measured plays straight). Run it after adding titles; it only does what's
new (`--redo --only ID` to measure a title again, `--copies 1` for first copies only).

The cartoon block has short breaks of its own instead: after every third programme, INTERVALO and VOLTAMOS (cards
only, about ten seconds), never in a slot's last four minutes (`catalog/grade.json` › `block_breaks`; they go in the
schedule as ordinary pieces of ours, so every app version plays them).

## The day

Since 31 October 2026 the day has parts (Niko): cartoons from 06:00 to 13:30; the matinee in the afternoon (silent
comedy, serials, then comedy or westerns on alternate days, Kung Fu de Sábado at 15:00 on Saturdays) until 19:00;
the great films in prime time (great classics or adventure from 19:00, noir from 22:00); and the madrugada (horror,
science fiction / cult / documentaries, classic TV). `catalog/grade.json` › `dayparts` names them and the schedule
carries them (`dayparts`), so the site's guide heads the day with them; the apps ignore them.

`build.py` lays a feature out as its running time plus its breaks, then `tools/segments.py` cuts it into parts.
A break is **our own pieces only**. Since 31 October 2026 (Niko's call) it is just the INTERVALO card and VOLTAMOS,
about ten seconds: no trailers, no promos, no sponsor slot (future spots will be our own, voiced by Niko). For those,
`grade.json` › `breaks` › `hold` gives each break that many seconds of the station card, which the Estúdio's spots
replace; `slot`, `promos`, `trailers: true` and `idents: true` bring the old pieces back (`tools/segments.py`).
The game trailers are out of rotation everywhere, not only in breaks.
In `schedule2.json` (format 2) a part is `[start, end, id, block, part]` (0, 1...), a break piece has part -1, and
each copy of a split title carries `cuts` (ms of that copy's file). The app pauses on the cut's frame, preloads the
return (0.3.2: about a minute before the break, since a ten-second break is too short) and resumes seamlessly; the guide shows the feature as one programme.

`catalog/grade.json`: `breaks.on: false` puts every feature back in one piece. `commercial_mode` (off; for when
the breaks carry paid ads) puts on the air only the titles cleared for that use (`rights`).

## Subtitles (legendas)

KÖLJA TV makes its own subtitles: Portuguese (pt-BR) for everything we subtitle, and English for the talkies.
Silent films get Portuguese for their intertitles, letters and newspapers, shown for as long as the card is on
screen; cartoons only where the speech or a song matters. The files live in `public/legendas/` and are published
with the site.

`legendas/index.json`:

```json
{"v": 1, "langs": {"pt-BR": "Português", "en": "English"},
 "titles": {"<id>": {"langs": ["pt-BR", "en"], "r": "<revision>",
                     "copies": {"<fnv1a-32 of the copy's url>": {"s": 1.0, "map": [[0, 0.0], [1830.2, 4.4]]}}}}}
```

The subtitles are timed on one copy of the title. Every other copy is lined up with it: the subtitle time is
`(t - offset) / s` for the copy's file time `t`, the offset stepping at the copy times listed in `map` (a copy may
run at another speed, start earlier, or miss a reel). A copy that isn't listed plays without subtitles rather than
out of sync. The players (the site's `tv/tv.js` and Retrotv 0.3.3+) read the index, fetch a title's `.vtt` when it
goes on the air (by `r`, so a fixed file is fetched again), and draw the line on the glass. Default Portuguese; the
viewer picks PT / EN / OFF (site: the CC button under the set or the C key; Retrotv: MENU › LEGENDAS).

To fix a line: edit the `.vtt` (keep the timing format), commit and push; the index's `r` for that title should
change too (any new value), so phones that kept the old file fetch it again.

## Estúdio KÖLJA TV (running the channel by hand, no AI needed)

`estudio/` is a local web app for Niko to run the channel alone: own programmes (recurring slots, episodes
converted with ffmpeg, opening/closing vignettes drawn by `estudio/vinheta.py` with the `make_idents.py` toolkit),
the week's grade (remove, insert, move, preview any second, the day's blocks), the films (search, off/on, copies,
break points), paid spots with a per-day/per-block report, link health with one-click swaps, Publicar (uploads our
videos to the `estudio-midia` release, commits `catalog/`, pushes, tags `pub-*`) and Desfazer
(publishes an earlier `pub-*` again). Python standard library only; the GitHub token lives in the macOS Keychain.
Manual (Portuguese): `estudio/web/manual.pdf`, source `estudio/manual/manual.html`.

- Install on a Mac: double-click `estudio/instalar.command` (makes the Desktop app); run: the Desktop app, or
  `python3 estudio/estudio.py` (http://127.0.0.1:8799).
- What it writes: `catalog/programas.json`, `catalog/anuncios.json`, `catalog/grade_manual.json` (plus the existing
  `titles.json`, `breaks.json`, `grade.json` › `day`). `tools/proprios.py` reads them inside `build.py`: programmes and a
  date's inserts are cut into the day's slots, removed titles keep their turn on the tape, spots replace our own pieces
  inside the features' breaks (same break length). With none of these files the schedule is byte-for-byte what it
  was without the Estúdio.
- Videos stay in `media/programas/` and `media/anuncios/` (not in git) until published.
- Tests use `KTV_TEST_UPLOAD_DIR` (uploads become copies in a folder, no token checks) with a local bare repo as `origin`.

## Fixing things by hand

Edit `catalog/titles.json` on GitHub (pencil icon) and commit; the workflow rebuilds in a minute or two.

- dead copy: delete its `{"url": ..., "dur": ...}` line, or move a better one to the top of `sources`
- new copy: add `{"url": "https://.../<file>.mp4", "dur": <seconds>}` at the top
- pull a title from the air (keeping its record): add `"off": true`

From a terminal the same is `python3 tools/fix.py <id> --url URL`, `--drop URL`, `--off`, `--on`.
`"dur"` on the title itself is its slot length: leave it, so the rest of the day doesn't move.

## Adding titles

Titles are added through the Estúdio (Filmes › Incluir filme). After adding, `python3 tools/build.py` shows the effect
locally and `python3 tools/rotation.py` how long the channel now goes without a rerun. A new block needs its name in
`catalog/grade.json` › `blocks`, slots in `day` (size them to the block's shelf: hours on the shelf ÷ hours a
day = days before its first rerun) and, if it has one, a vignette in `ours`.

Our pieces: `~/ComfyUI/.venv/bin/python3 tools/make_idents.py` (PIL + numpy, drawn and synthesised from scratch,
into `media/ours/`), add new ones to `catalog/grade.json` › `ours`, then `tools/release_ours.sh --clobber` (it uploads the files `ours` names, nothing else). Keep `media/ours/` backed up, it isn't
in git.

Special nights: `catalog/grade.json` › `special` gives a date (MM-DD) a day of its own, and a slot's `pin` lists
the titles that open it, in order (31 October: SESSÃO TERROR from 19:00 with Nosferatu, Night of the Living Dead
and Carnival of Souls).

The app's seed: Retrotv ships a 7-day copy of the schedule so a fresh install has a channel before its first
fetch. Before building an APK: `python3 tools/build.py --days 7 --out /tmp/seed` and copy `/tmp/seed/schedule2.json`
to `retrofone-spinoffs/tv/src/main/assets/koljatv/schedule.json` (0.3.1+ read format 2; 0.3.0 took `schedule.json`).

## Where our own media lives, and why

Today: 19 pieces on the air, about 5.5 MB in total (the largest, the station card, is 0.9 MB). The app keeps each piece on the
phone after its first download, so a phone fetches ~5.5 MB once, not per showing; even uncached, an hour of viewing
would pull ~3-5 MB of our pieces.

| option | limits that matter | fit |
|---|---|---|
| **GitHub Releases assets** (chosen, 03:50 decision) | ≤ 2 GiB per file, no published bandwidth cap; served by redirect to objects.githubusercontent.com; outside git history | Nothing heavy in git, room to grow into long KÖLJA shows. |
| Pages, in the repo | site ≤ 1 GB, ~100 GB/month bandwidth (soft, ~20,000 viewer-hours of our pieces); git warns at 50 MB and blocks 100 MB files | Would fit today, but every new trailer stays in git history forever. |
| Git LFS | free plan: small storage and bandwidth quota, paid beyond | No: the bandwidth quota is the thing we'd hit. |
