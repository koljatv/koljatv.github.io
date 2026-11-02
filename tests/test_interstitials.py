"""Editorial shorts must only consume filler, preserving every programme's clock."""
import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build

class InterstitialTests(unittest.TestCase):
    def setUp(self):
        self.cfg = build.load('catalog/grade.json')
        self.cfg['ours'].append({'id': 'test_neco', 'kind': 'promo', 'dur': 12,
                                 'title': 'NECO', 'file': 'neco.mp4'})
        self.cfg['interstitials'] = [{'id': 'test_neco', 'since': '2026-11-02T18:09:00-03:00',
            'windows': [['06:00', '14:00'], ['14:00', '20:00'], ['20:00', '24:00']],
            'min_gap_minutes': 240}]
        self.g = build.Grade(self.cfg, build.load('catalog/titles.json'), {}, build.load('catalog/breaks.json'))
        self.day = (dt.date(2026, 11, 3) - dt.date(1970, 1, 1)).days
        self.base = self.g.midnight(self.day)

    def place(self, items):
        import interstitials
        return interstitials.place(items, self.cfg, self.base, build.Prog)

    def card(self, minute, seconds=30, part=None):
        a = self.base + minute * 60000
        return [a, a + seconds * 1000, self.g.card, 'toons'] + ([] if part is None else [part])

    def test_preserves_programmes_and_uses_exactly_twelve_seconds(self):
        a = self.card(800)
        p = build.Prog('film', 'film', 60, 'toons')
        film = [a[1], a[1] + 60000, p, 'toons']
        result = self.place([a, film])
        neco = [x for x in result if x[2].id == 'test_neco']
        self.assertEqual(len(neco), 1)
        self.assertEqual(neco[0][1] - neco[0][0], 12000)
        self.assertEqual(result[-1], film)
        self.assertEqual(a, self.card(800))  # do not mutate the source schedule
        self.assertEqual(result[0][0], a[0])
        self.assertTrue(all(x[1] == y[0] for x, y in zip(result, result[1:])))

    def test_does_not_truncate_or_use_feature_breaks(self):
        items = [self.card(800, 11.9), self.card(850, 30, -1)]
        self.assertEqual(self.place(items), items)

    def test_exact_fit_has_no_zero_length_card(self):
        result = self.place([self.card(800, 12)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][2].id, 'test_neco')

    def test_at_most_three_and_four_hour_spacing(self):
        result = self.place([self.card(m) for m in [700, 800, 850, 950, 1000, 1200, 1250, 1430]])
        shorts = [x for x in result if x[2].id == 'test_neco']
        self.assertEqual(len(shorts), 3)
        self.assertTrue(all(y[0]-x[0] >= 240*60000 for x,y in zip(shorts,shorts[1:])))

    def test_since_approval_and_disabled_config(self):
        self.cfg['interstitials'][0]['since'] = '2026-11-03T18:09:00-03:00'
        items = [self.card(800), self.card(1100)]
        self.assertEqual([x[0] for x in self.place(items) if x[2].id == 'test_neco'], [items[1][0]])
        self.cfg.pop('interstitials')
        self.assertEqual(self.place(items), items)

    def test_integration_preserves_non_card_items(self):
        with_short, _ = self.g.items(self.day)
        self.cfg.pop('interstitials')
        plain = build.Grade(self.cfg, build.load('catalog/titles.json'), {}, build.load('catalog/breaks.json'))
        without, _ = plain.items(self.day)
        serial = lambda items: [[x[0],x[1],x[2].id,*x[3:]] for x in items if x[2].id not in ('cartao','test_neco')]
        self.assertEqual(serial(with_short), serial(without))
        self.assertTrue(any(x[2].id == 'test_neco' for x in with_short))

if __name__ == '__main__': unittest.main()
