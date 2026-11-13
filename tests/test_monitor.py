import importlib.util, pathlib, unittest
P=pathlib.Path(__file__).resolve().parents[1]/'tools/monitor.py'
class MonitorTests(unittest.TestCase):
 def test_missing_checker(self):
  self.assertTrue(P.exists(),'Public health monitor is missing')
 def test_validation_detects_expired_gaps_mismatch_and_stale_pointer(self):
  if not P.exists(): self.skipTest('monitor not implemented')
  spec=importlib.util.spec_from_file_location('monitor',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  now=100000000
  s={'rev':'a','from':now-1000,'to':now+8*86400000,'titles':{'film':{}},'ours':{},'items':[[now-1000,now+8*86400000,'film','toons']]}
  n={'rev2':'a','generated':now}
  self.assertEqual(m.validate(s,n,now),[])
  self.assertTrue(any('revision' in e for e in m.validate(s,dict(n,rev2='b'),now)))
  self.assertTrue(any('expired' in e for e in m.validate(s,n,s['to']+1)))
  self.assertTrue(any('stale' in e for e in m.validate(s,dict(n,generated=now-13*3600000),now)))
  broken=dict(s,items=[[now-1000,now+10,'film','toons'],[now+11,s['to'],'film','toons']])
  self.assertTrue(any('gap' in e for e in m.validate(broken,n,now)))
 def test_bad_rows_are_errors_not_crashes(self):
  if not P.exists(): self.skipTest('monitor not implemented')
  spec=importlib.util.spec_from_file_location('monitor',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  self.assertTrue(m.validate({'items':[None]}, {}, 0))
