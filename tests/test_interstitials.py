"""NECO has exact daily appointments, even with weather and growing paid breaks."""
import copy
import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build

class InterstitialTests(unittest.TestCase):
    def setUp(self):
        self.cfg = build.load('catalog/grade.json')
        self.cfg['interstitials'] = [{'id': 'neco', 'since': '2026-11-02T18:09:00-03:00',
                                     'at': ['13:29', '18:59', '23:59']}]
        self.titles = build.load('catalog/titles.json')
        self.cuts = build.load('catalog/breaks.json')
        self.day = (dt.date(2026, 11, 2) - dt.date(1970, 1, 1)).days

    def grade(self, cfg=None, **kw):
        return build.Grade(cfg or self.cfg, self.titles, kw.pop('health', {}), self.cuts, **kw)

    def test_exact_daily_times_for_56_days_both_formats_weather_ads_and_health(self):
        extra = {'anuncios': [{'id': 'qa', 'nome': 'QA', 'url': 'https://example.invalid/qa.mp4',
                 'dur': 180, 'por_dia': 20, 'inicio': '2026-11-02', 'fim': '2026-12-31'}]}
        health = {s['url']: {'ok': False} for t in self.titles
                  if t['id'] in ('kansas-pacific-1953', 'the-last-man-on-earth-1964') for s in t['sources']}
        for fmt in (1, 2):
            for weather in (False, True):
                cfg = copy.deepcopy(self.cfg)
                cfg['breaks']['on'] = fmt == 2
                g = self.grade(cfg, health=health, extra=extra)
                g.tempo.renders = list(range(g.midnight(self.day), g.midnight(self.day+56), 6*3600000)) if weather else []
                for day in range(self.day, self.day+56):
                    with self.subTest(fmt=fmt, weather=weather, day=day):
                        items, _ = g.items(day)
                        shorts = [x for x in items if x[2].id == 'neco']
                        expected = [809, 1139, 1439] if day > self.day else [1139, 1439]
                        self.assertEqual([x[0]-g.midnight(day) for x in shorts], [m*60000 for m in expected])
                        self.assertTrue(all(x[1]-x[0] == 12000 and len(x) == 4 for x in shorts))
                        self.assertTrue(all(x[1] == y[0] for x,y in zip(items,items[1:])))
                        self.assertEqual(items[0][0], g.midnight(day))
                        self.assertEqual(items[-1][1], g.midnight(day+1))
                        for x in items:
                            self.assertGreater(x[1], x[0])
                            if len(x) == 4 and x[2].kind != 'card':
                                self.assertEqual(x[1]-x[0], x[2].dur)
                        for minute in (810,1140):
                            self.assertTrue(any(x[0] == g.midnight(day)+minute*60000 and x[2].kind == 'vignette' for x in items))

    def test_disabled_and_before_approval_keep_previous_layout(self):
        plain = copy.deepcopy(self.cfg); plain.pop('interstitials')
        serial = lambda xs: [[x[0],x[1],x[2].id,*x[3:]] for x in xs]
        a,_ = self.grade().items(self.day-1)
        b,_ = self.grade(plain).items(self.day-1)
        self.assertEqual(serial(a), serial(b))

    def test_paid_break_cannot_borrow_past_fixed_appointment(self):
        g = self.grade()
        p = build.Prog('neco', 'promo', 12, fixed=True)
        items = [[0,1000,g.card,'noir',-1], [1000,13000,p,'noir'], [13000,61000,g.card,'noir']]
        self.assertIsNone(g.own._spare(items, [0,0]))

    def test_invalid_or_conflicting_appointments_fail_build(self):
        for times in (['13:29','13:29'], ['25:00'], ['13:00'], ['13:29:59']):
            with self.subTest(times=times):
                cfg = copy.deepcopy(self.cfg);cfg['interstitials'][0]['at'] = times
                with self.assertRaises(ValueError): self.grade(cfg).items(self.day+1)

if __name__ == '__main__': unittest.main()
