"""The approved second episode uses full-length slots away from NECO."""
import copy
import unittest
import test_sadim
from test_sadim import build

ID = 'sadim-el-moscon-2026'

class SadimEpisodeTwoTests(unittest.TestCase):
    setUp = test_sadim.SadimTests.setUp
    def test_ep02_launch_rotation_and_spacing(self):
        t = next((t for t in self.titles if t['id'] == ID), None)
        self.assertIsNotNone(t)
        self.assertEqual(t['dur'], 124.375)
        self.assertEqual(t['sha256'], '8cf0bc19eaf4f14f124cce967032b935c2b469704aaf13e251a2b34c6eeff015')
        for fmt in (1, 2):
            for weather in (False, True):
                cfg = copy.deepcopy(self.cfg); cfg['breaks']['on'] = fmt == 2
                extra = copy.deepcopy(self.extra)
                extra['anuncios'] = [{'id':'qa','nome':'QA','url':'https://example.invalid/qa.mp4','dur':180,'por_dia':20,'inicio':'2026-11-02','fim':'2026-12-31'}]
                g = build.Grade(cfg, self.titles, {t['sources'][0]['url']:{'ok':False}}, self.cuts, extra)
                g.tempo.renders = list(range(g.midnight(self.day), g.midnight(self.day+56), 6*3600000)) if weather else []
                count = 0
                for d in range(self.day, self.day+56):
                    items, _ = g.items(d)
                    eps = [x for x in items if x[2].id == ID]
                    self.assertLessEqual(len(eps), 2)
                    if d in (self.day+1,self.day+2):
                        self.assertEqual([x[0]-g.midnight(d) for x in eps], [725*60000+3600])
                    for x in eps:
                        self.assertEqual(x[1]-x[0], 124375)
                        for nd in (d-1,d,d+1):
                            for at,p in build.interstitials.appointments(cfg,g.midnight(nd),build.Prog):
                                if p.id == 'neco':
                                    self.assertGreaterEqual(max(at-x[1],x[0]-(at+p.dur)),3600000)
                    count += len(eps)
                self.assertGreaterEqual(count, 2)
                self.assertLess(count, 20)

    def test_ep02_dead_sources_keep_full_slot(self):
        t = next((t for t in self.titles if t['id'] == ID), None)
        self.assertIsNotNone(t)
        g = build.Grade(self.cfg,self.titles,{s['url']:{'ok':False} for s in t['sources']},self.cuts,self.extra)
        xs,_ = g.items(self.day+1)
        start = g.midnight(self.day+1)+725*60000+3600
        slot = [x for x in xs if start <= x[0] < start+124375]
        self.assertEqual(slot[0][0], start)
        self.assertEqual(slot[-1][1], start+124375)
        self.assertTrue(all(x[2].id != ID for x in slot))
        self.assertTrue(all(a[1] == b[0] for a,b in zip(xs,xs[1:])))
