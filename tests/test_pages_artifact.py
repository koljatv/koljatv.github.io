import pathlib,re,unittest
WORKFLOW=(pathlib.Path(__file__).resolve().parents[1]/'.github/workflows/grade.yml').read_text()
def input_value(action,key,default):
 section=re.search(r'uses: actions/'+action+r'@[^\n]+(?P<body>.*?)(?=\n      - |\Z)',WORKFLOW,re.S).group('body')
 found=re.search(r'^\s+'+key+r':\s*(.+)$',section,re.M)
 return found.group(1).strip() if found else default
def expand(value,attempt):
 return value.replace('${{ github.run_id }}','1234').replace('${{ github.run_attempt }}',str(attempt))
class PagesArtifactTests(unittest.TestCase):
 def test_retry_does_not_match_previous_attempt_artifact(self):
  upload=input_value('upload-pages-artifact','name','github-pages')
  deploy=input_value('deploy-pages','artifact_name','github-pages')
  self.assertEqual(expand(upload,2),expand(deploy,2))
  self.assertNotEqual(expand(upload,1),expand(deploy,2))
