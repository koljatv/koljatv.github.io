"""Fixed editorial appointments in the final minute of existing blocks.

The builder reserves the closing minute before selecting whole programmes. Weather
and paid breaks can use only the capacity before the appointment, never move it.
"""
import datetime as dt
import re

MIN = 60_000


def appointments(cfg, midnight, Prog):
    by = {o['id']: o for o in cfg['ours']}
    out = []
    for rule in cfg.get('interstitials', []):
        o = by[rule['id']]
        p = Prog(o['id'], o['kind'], o['dur'], fixed=True, series=o.get('series', o['id']))
        since = dt.datetime.fromisoformat(rule['since'])
        if since.tzinfo is None or not 0 < p.dur <= MIN or not rule.get('at'):
            raise ValueError('Fixed appointments need times, a zoned start date and a duration <= 60s')
        rotation = rule.get('rotation')
        if rotation:
            anchor = dt.datetime.fromisoformat(rotation['since'])
            ids = rotation['ids']
            if anchor.tzinfo is None or not ids or len(set(ids)) != len(ids):
                raise ValueError('Rotation needs distinct episode ids and a zoned start date')
            if any(i not in by or not 0 < by[i]['dur'] <= 60 for i in ids):
                raise ValueError('Rotation episodes must exist and last <= 60s')
            local_day = dt.datetime.fromtimestamp(midnight / 1000, anchor.tzinfo).date()
            days = (local_day - anchor.date()).days
            first_times = sum(hm + ':00' < anchor.strftime('%H:%M:%S') for hm in rule['at'])
        for index, hm in enumerate(sorted(rule['at'])):
            if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', hm):
                raise ValueError('Fixed appointment must use HH:MM local time')
            h, m = map(int, hm.split(':'))
            at = midnight + (h * 60 + m) * MIN
            selected = p
            if rotation and at >= int(anchor.timestamp() * 1000):
                episode = by[ids[(days * len(rule['at']) + index - first_times) % len(ids)]]
                selected = Prog(episode['id'], episode['kind'], episode['dur'], fixed=True,
                                series=o.get('series', o['id']))
            if at >= int(since.timestamp() * 1000): out.append((at, selected))
    out.sort(key=lambda x: x[0])
    if any(a + p.dur > b for (a, p), (b, _) in zip(out, out[1:])):
        raise ValueError('Fixed appointments overlap')
    return out
