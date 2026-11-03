"""Both approved Neco episodes retain appointments and all surrounding programmes."""
import copy
import datetime as dt
import unittest
import test_sadim
from test_sadim import build

ID = 'neco-ep02-tentaculo-2026'
class NecoEpisodeTwoTests(unittest.TestCase):
    setUp = test_sadim.SadimTests.setUp

    def test_rotation_keeps_boundaries_and_every_other_programme(self):
        old = copy.deepcopy(self.cfg)
        old['interstitials'][0].pop('rotation', None)
        for fmt in (1, 2):
            cfg = copy.deepcopy(self.cfg); cfg['breaks']['on'] = fmt == 2
            prior = copy.deepcopy(old); prior['breaks']['on'] = fmt == 2
            g = build.Grade(cfg,self.titles,{},self.cuts,self.extra)
            before = build.Grade(prior,self.titles,{},self.cuts,self.extra)
            serial = lambda xs: [[x[0],x[1],x[2].id,*x[3:]] for x in xs if x[2].kind not in ('card','promo')]
            for d in range(self.day, self.day+56):
                xs,_ = g.items(d); ys,_ = before.items(d)
                self.assertEqual(serial(xs), serial(ys))
                eps = [x for x in xs if x[2].id in ('neco',ID)]
                expected = ['neco','neco'] if d == self.day else [([ID,'neco'])[((d-self.day-1)*3+i)%2] for i in range(3)]
                self.assertEqual([x[2].id for x in eps],expected)
                self.assertEqual([x[0]-g.midnight(d) for x in eps],[m*60000 for m in ([1139,1439] if d==self.day else [809,1139,1439])])
                self.assertTrue(all(a[1]==b[0] for a,b in zip(xs,xs[1:])))
                for x in eps:
                    self.assertEqual(x[1]-x[0],10000 if x[2].id==ID else 12000)
                    card=xs[xs.index(x)+1]
                    self.assertEqual((card[2].kind,card[1]-x[0]),('card',60000))

    def test_spacing_protects_episode_two_and_midnight(self):
        g=build.Grade(self.cfg,self.titles,{},self.cuts,self.extra)
        p=g.titles['sadim-cha-mosca-2026']
        midnight=g.midnight(self.day+2) # preceding 23:59 is EP02
        self.assertFalse(g.spacing_ok(p,midnight+59*60000+9999))
        self.assertTrue(g.spacing_ok(p,midnight+59*60000+10000))
        at=g.midnight(self.day+1)+809*60000
        self.assertFalse(g.spacing_ok(p,at-p.span-3600000+1))
        self.assertTrue(g.spacing_ok(p,at-p.span-3600000))

    def test_exact_approved_media_catalogued(self):
        t=next(t for t in self.cfg['ours'] if t['id']==ID)
        self.assertEqual(t['dur'],10)
        self.assertEqual(t['sha256'],'626302539c078263ed4c4998ba82f9607aa721523111cdb19cbd131a97f3613e')
        self.assertEqual(t['series'],'neco')
        self.assertNotIn('Niko',str(t))

    def test_rotation_is_stable_on_restart_and_rejects_invalid_media(self):
        day=self.day+2
        g=build.Grade(self.cfg,self.titles,{},self.cuts,self.extra)
        self.assertEqual([p.id for _,p in build.interstitials.appointments(self.cfg,g.midnight(day),build.Prog)],['neco',ID,'neco'])
        for ids in ([],['missing'],[ID,ID]):
            cfg=copy.deepcopy(self.cfg);cfg['interstitials'][0]['rotation']['ids']=ids
            with self.assertRaises(ValueError):build.interstitials.appointments(cfg,g.midnight(day),build.Prog)
        cfg=copy.deepcopy(self.cfg)
        cfg['interstitials'][0]['rotation']['since']='2026-11-03T13:29:30-03:00'
        self.assertEqual([p.id for _,p in build.interstitials.appointments(cfg,g.midnight(self.day+1),build.Prog)],['neco',ID,'neco'])
