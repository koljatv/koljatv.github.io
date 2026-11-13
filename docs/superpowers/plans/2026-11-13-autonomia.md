# Kölja TV autonomous recovery implementation plan

Approved by Niko on 2026-11-13 at 18:11 BRT: retain free infrastructure, reserve schedule, automatic recovery and health monitoring. Implementation and publication authorized by the current repair request and approval. No paid services or new accounts.

**Goal:** Continue playback through schedule/pointer failure and recover publication without an AI session or this Mac.
**Architecture:** Keep Pages/Actions and existing player. Atomic, validated schedule loading with last-good browser storage and direct-file fallback. Existing reserve video engine also covers missing/expired schedules, returning to real schedule on recovery. Seven-day published schedule. Bounded Actions recovery and public endpoint verification; one deduplicated GitHub incident for persistent failures.
**Stack:** Vanilla JS, Python stdlib, existing GitHub Actions.

## Work and checks
- [x] Preserve original dirty checkout; isolate from origin/main; run existing Python suite.
- [x] Reproduce missing now.json, expired schedule, and both unavailable after warm cache in a silent browser. Test actual served player with local deterministic video, not simulated video APIs.
- [x] Fix getJSON timeout, single-flight load, validate before assignment, fallback to direct schedule and last-good cache. Persist only validated schedule; handle blocked/full browser storage.
- [x] Generalize reserve mode to missing/expired schedule and load reserve independently. Do not loop stale weather or claim old appointments are current. Return to schedule when available; keep power-off effective.
- [x] Publish seven days in both existing formats; validate continuity and schedule references before deployment. Reserve list refresh is bounded, preserves last-good on failure and does not publish empty lists.
- [x] Add monitor that verifies public now/revisions/coverage/assets after deployment and periodically. Retry failed workflow once, open/update one incident and close on recovery. Document scheduler/outage limitations.
- [x] Run regression suite, desktop/mobile browser outage/recovery tests and live-media smoke test. Inspect screenshots. Preserve catalogue and media hashes.
- [x] Review diff, publish approved changes from latest main without unrelated edits, verify deployed files and workflow result, save receipts and report remaining external dependencies.

Commands: `python3 -m unittest discover -s tests -v`; browser regression `python3 tests/player_recovery.py`; production check `python3 tools/monitor.py --base https://tv.kolja.com.br/`.
Evidence: original diagnostic captures in /Users/macos/Documents/Developer/koljatv-audit-20261113. No new expenditure; no changes to programmes or prior approvals.

Pre-publication verification: 20 Python tests, 4 Node tests, 8 real-decode browser outage/recovery cases; both generated formats continuous for seven days; actionlint clean. Live media (Royal Wedding) played on desktop/mobile with no page errors or horizontal overflow. Independent review found three issues (emergency local fallback, stale retry checkout, premature incident closure); all corrected and reviewed. Original dirty checkout preserved.

Publication confirmed: grade run 43510526967 succeeded; automatic health run 43510858966 succeeded. Public player and HTML SHA256 matched candidate files. Published schedule e1cc7cc55d11 spans seven calendar days; 41 verified reserve titles. Public monitor returned ok=true. Evidence retained outside the repository in the diagnostic folder noted above.
