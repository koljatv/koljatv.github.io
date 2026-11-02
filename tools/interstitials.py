"""Occasional editorial shorts in existing station-card gaps, never inside programmes.

One complete showing per configured daily window at most. No programme, weather
segment, advert or block boundary moves: only a normal closing card gives up time.
Window bounds must also leave min_gap_minutes between the last window of a day
and the first of the next, so independently rebuilt dates retain the same spacing.
"""
import datetime as dt

MIN = 60_000


def minute(hm):
    h, m = map(int, hm.split(':'))
    return h * 60 + m


def place(items, cfg, midnight, Prog):
    by = {o['id']: o for o in cfg['ours']}
    for rule in cfg.get('interstitials', []):
        o = by[rule['id']]
        p = Prog(o['id'], o['kind'], o['dur'])
        gap = int(rule['min_gap_minutes']) * MIN
        windows = [(minute(a), minute(b)) for a, b in rule['windows']]
        if not windows or p.dur <= 0 or gap < 0:
            raise ValueError('Interstitial needs positive duration and daily windows')
        if any(not 0 <= a < b <= 1440 for a, b in windows) or any(
                b > c for (_, b), (c, _) in zip(windows, windows[1:])):
            raise ValueError('Interstitial windows must be ordered and disjoint')
        if (1440 - windows[-1][1] + windows[0][0]) * MIN < gap:
            raise ValueError('Interstitial windows must preserve the gap across midnight')
        since = int(dt.datetime.fromisoformat(rule['since']).timestamp() * 1000)
        last = None
        for start, end in windows:
            earliest = max(midnight + start * MIN, since,
                           last + gap if last is not None else 0)
            latest = midnight + end * MIN
            for k, it in enumerate(items):
                if len(it) != 4 or it[2].kind != 'card':
                    continue  # never use a card inside a feature's commercial break
                t = max(it[0], earliest)
                if t + p.dur > min(it[1], latest):
                    continue
                replacement = []
                if it[0] < t:
                    replacement.append([it[0], t, *it[2:]])
                replacement.append([t, t + p.dur, p, it[3]])
                if t + p.dur < it[1]:
                    replacement.append([t + p.dur, it[1], *it[2:]])
                items = items[:k] + replacement + items[k + 1:]
                last = t
                break
    return items
