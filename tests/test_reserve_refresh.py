import importlib.util,json,pathlib,tempfile,unittest
P=pathlib.Path(__file__).resolve().parents[1]/'tools/reserva.py'
spec=importlib.util.spec_from_file_location('reserva',P);r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class ReserveRefreshTests(unittest.TestCase):
 def test_failed_refresh_preserves_previous_file(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'reserve.json';p.write_text('{"items":[{"id":"old"}]}');original=p.read_bytes()
   self.assertFalse(r.save_reserve([],str(p)))
   self.assertEqual(p.read_bytes(),original)
 def test_success_replaces_atomically(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'reserve.json';items=[{'id':'new','copies':['https://example.com/a.mp4']}]
   self.assertTrue(r.save_reserve(items,str(p)))
   self.assertEqual(json.loads(p.read_text())['items'],items)
   self.assertFalse(pathlib.Path(str(p)+'.tmp').exists())
