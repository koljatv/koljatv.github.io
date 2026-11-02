"""Fetch pinned CC0 samples and portable macOS renderer, checking every SHA-256."""
from pathlib import Path
import hashlib,json,tarfile,urllib.request
ROOT=Path(__file__).resolve().parent; VENDOR=ROOT/'vendor'
def fetch(url,dest,expected):
 if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest()==expected:return
 data=urllib.request.urlopen(url,timeout=60).read()
 assert hashlib.sha256(data).hexdigest()==expected,('download hash mismatch',url)
 dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
manifest=json.loads((VENDOR/'asset-manifest.json').read_text())
for row in manifest['samples']:fetch(row['url'],VENDOR/'samples'/row['file'],row['sha256'])
engine=json.loads((VENDOR/'engine-manifest.json').read_text());archive=VENDOR/'sfizz-engine.tar.gz'
fetch(engine['url'],archive,engine['sha256'])
if not (VENDOR/'sfizz-1.2.3-macos/usr/local/bin/sfizz_render').exists():
 with tarfile.open(archive) as tar:
  for member in tar.getmembers():
   assert not member.name.startswith('/') and '..' not in Path(member.name).parts
  tar.extractall(VENDOR,filter='data')
print('Verified 8 CC0 samples and sfizz1.2.3; no system plugin installation.')
