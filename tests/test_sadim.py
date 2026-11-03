"""Approved short: complete airings, measured launch slots and existing boundaries."""
import copy
import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build
import proprios

ID = 'sadim-cha-mosca-2026'
class SadimTests(unittest.TestCase):
    def setUp(self):
        self.cfg = build.load('catalog/grade.json')
        self.titles = build.load('catalog/titles.json')
        self.cuts = build.load('catalog/breaks.json')
        self.extra = proprios.load_extra(build.load)
        self.day = (dt.date(2026,11,2)-dt.date(1970,1,1)).days

    def test_approved_catalogue_and_delivery_sources(self):
        found = [t for t in self.titles if t['id'] == ID]
        self.assertEqual(len(found), 1)
        t = found[0]
        self.assertEqual((t['title'],t['kind'],t['dur']), ('As Aventuras de Sadim, o Mago','short',78))
        self.assertIn('Produção: Kölja Arts', t['synopsis_pt'])
        self.assertNotIn('Niko', str(t))
        self.assertEqual(t['sha256'], '2c43d174e6db0df1e3e717fa38a55ea2d13dde57979c3910c7c14d1015178641')
        self.assertEqual(len(t['sources']), 2)
        self.assertTrue(t['sources'][0]['url'].startswith('https://tv.kolja.com.br/tv/ours/'))
        self.assertTrue(t['sources'][1]['url'].startswith(self.cfg['ours_base']))
        self.assertTrue(all(s['dur'] == 78 for s in t['sources']))

    def test_release_order_and_all_sources_unavailable_preserve_slot(self):
        t = next(t for t in self.titles if t['id'] == ID)
        health = {t['sources'][0]['url']: {'ok': False}}
        g = build.Grade(self.cfg, self.titles, health, self.cuts, self.extra)
        self.assertEqual(build.sources(t, g)[0]['url'], t['sources'][1]['url'])
        health = {s['url']: {'ok': False} for s in t['sources']}
        g = build.Grade(self.cfg, self.titles, health, self.cuts, self.extra)
        d = self.day + 1
        items, _ = g.items(d)
        self.assertFalse(any(x[2].id == ID for x in items))
        start = g.midnight(d) + 720 * 60000 + 3600
        slot = next(x for x in items if x[0] == start)
        self.assertEqual((slot[2].kind, slot[1] - slot[0]), ('card', 78000))
        self.assertTrue(all(a[1] == b[0] for a, b in zip(items, items[1:])))
        self.assertTrue(any(x[0] == g.midnight(d) + 809 * 60000 and x[2].id == 'neco' for x in items))

    def test_spacing_across_midnight_and_health_substitutes(self):
        g = build.Grade(self.cfg, self.titles, {}, self.cuts, self.extra)
        p = g.titles[ID]
        midnight = g.midnight(self.day+2)
        # Previous day's 23:59 NECO ends at 23:59:12: full 60 minutes required.
        self.assertFalse(g.spacing_ok(p, midnight+59*60000))
        self.assertTrue(g.spacing_ok(p, midnight+59*60000+12000))
        before = midnight+809*60000-p.span-60*60000
        self.assertTrue(g.spacing_ok(p, before))
        self.assertFalse(g.spacing_ok(p, before+1))
        # Force a dead title to use Sadim as its only available replacement.
        dead = build.Prog('dead', 'cartoon', 180, 'toons')
        g.shelves = {'toons': [p]}; g.fillers = [p]
        near = midnight+808*60000
        items, _ = g.patch([[near, near+180000, dead, 'toons']])
        self.assertFalse(any(x[2].id == ID for x in items))
        far = midnight+720*60000
        items, _ = g.patch([[far, far+180000, dead, 'toons']])
        self.assertEqual(items[0][2].id, ID)
        self.assertEqual(items[0][1]-items[0][0], 78000)

    def test_manual_spacing_conflict_fails_instead_of_publishing(self):
        extra = copy.deepcopy(self.extra)
        extra['manual']['inserir'][0]['at'] = '13:27'
        g = build.Grade(self.cfg, self.titles, {}, self.cuts, extra)
        with self.assertRaisesRegex(ValueError, 'spacing'):
            g.items(self.day+1)

    def test_56_days_formats_weather_health_ads(self):
        self.assertTrue(any(t['id'] == ID for t in self.titles), 'Sadim missing from catalogue')
        for fmt in (1,2):
            for weather in (False, True):
                cfg=copy.deepcopy(self.cfg);cfg['breaks']['on']=fmt==2
                extra=copy.deepcopy(self.extra)
                extra['anuncios']=[{'id':'qa','nome':'QA','url':'https://example.invalid/qa.mp4','dur':180,'por_dia':20,'inicio':'2026-11-02','fim':'2026-12-31'}]
                # Dead first copy must retain the same full programme via the Release.
                t=next(t for t in self.titles if t['id']==ID)
                health={t['sources'][0]['url']:{'ok':False}}
                g=build.Grade(cfg,self.titles,health,self.cuts,extra)
                g.tempo.renders=list(range(g.midnight(self.day),g.midnight(self.day+56),6*3600000)) if weather else []
                docs=set(); airings=[]
                for d in range(self.day,self.day+56):
                    with self.subTest(fmt=fmt,weather=weather,day=d):
                        items,_=g.items(d)
                        self.assertEqual(items[0][0],g.midnight(d));self.assertEqual(items[-1][1],g.midnight(d+1))
                        self.assertTrue(all(a[1]==b[0] for a,b in zip(items,items[1:])))
                        for x in items:
                            self.assertGreater(x[1],x[0])
                            if len(x)==4 and x[2].kind!='card':self.assertEqual(x[1]-x[0],x[2].dur)
                            if x[2].block=='docs':docs.add(x[2].id)
                        sadim=[x for x in items if x[2].id==ID]
                        self.assertLessEqual(len(sadim),1)
                        self.assertTrue(all(x[1]-x[0]==78000 and len(x)==4 for x in sadim))
                        if d in (self.day+1,self.day+2):
                            self.assertEqual([x[0]-g.midnight(d) for x in sadim],[720*60000+3600])
                        neco=[x for x in items if x[2].id=='neco']
                        self.assertEqual([x[0]-g.midnight(d) for x in neco], [m*60000 for m in ([1139,1439] if d==self.day else [809,1139,1439])])
                        self.assertTrue(all(x[1]-x[0]==12000 for x in neco))
                        for x in sadim:
                            for nd in (d-1, d, d+1):
                                for at, p in build.interstitials.appointments(cfg, g.midnight(nd), build.Prog):
                                    if p.id == 'neco':
                                        self.assertGreaterEqual(max(at-x[1], x[0]-(at+p.dur)), 60*60000)
                        airings.extend(sadim)
                expected={t['id'] for t in self.titles if t['block']=='docs' and not t.get('off')}
                self.assertTrue(expected<=docs)
                self.assertGreaterEqual(len(airings),2);self.assertLess(len(airings),20)

if __name__ == '__main__': unittest.main()
