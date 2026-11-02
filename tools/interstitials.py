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
        p = Prog(o['id'], o['kind'], o['dur'], fixed=True)
        since = dt.datetime.fromisoformat(rule['since'])
        if since.tzinfo is None or not 0 < p.dur <= MIN or not rule.get('at'):
            raise ValueError('Fixed appointments need times, a zoned start date and a duration <= 60s')
        for hm in rule['at']:
            if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', hm):
                raise ValueError('Fixed appointment must use HH:MM local time')
            h, m = map(int, hm.split(':'))
            at = midnight + (h * 60 + m) * MIN
            if at >= int(since.timestamp() * 1000): out.append((at, p))
    out.sort(key=lambda x: x[0])
    if any(a + p.dur > b for (a, p), (b, _) in zip(out, out[1:])):
        raise ValueError('Fixed appointments overlap')
    return out
