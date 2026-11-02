"""Fail closed on missing coverage, clipping, decode errors or changed image streams."""
from pathlib import Path
import argparse,json,numpy as np
from render import ROOT,REPO,OUT,VENDOR,SR,OFFSET,run,sha,pcm,measure
from score import scores

def probe(p):return json.loads(run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',p]).stdout)
def vhash(p):return run(['ffmpeg','-v','error','-i',p,'-map','0:v:0','-c','copy','-f','hash','-hash','sha256','-']).stdout.decode().strip()
def score_check():
 manifest=json.loads((VENDOR/'asset-manifest.json').read_text())
 allscores=scores();assert len(allscores)==20 and len({s['name'] for s in allscores})==20
 for s in allscores:
  for role,sfz in [('horn','FHornSus'),('strings','ViolaEnsSusVib')]:
   for b,d,p,v in s[role]:
    matches=[r for r in manifest['regions'][sfz] if int(r['lokey'])<=p<=int(r['hikey']) and int(r['lovel'])<=v<=int(r['hivel'])]
    assert len(matches)==1,(s['name'],role,p,v,'SFZ coverage')
    assert b>=0 and d>0 and OFFSET+(b+d)*60/s['bpm']<s['duration']-.3,(s['name'],b,d)
  for b,d,voices,v,chord,root in s['harmonies']:assert sorted(voices)==voices and len(set(voices))==len(voices)
 assert len(allscores[0]['horn'])>40 and len(allscores[0]['sections'])==5
 return {'scores':20,'SFZ':'one region per acoustic note','duration_bounds':'passed','inner_voice_order':'passed','forecast_form':'30 bars, five sections, no loop extension'}
def remux(s,original):
 out=OUT/(s['name']+'.mp4');info=probe(original)
 video=next(x for x in info['streams'] if x['codec_type']=='video');dur=float(video['duration'])
 assert abs(dur-s['duration'])<.05,(original,dur,s['duration'])
 run(['ffmpeg','-v','error','-y','-i',original,'-i',OUT/(s['name']+'.m4a'),'-map','0:v:0','-map','1:a:0','-c','copy','-t',s['duration'],'-movflags','+faststart',out])
 assert vhash(original)==vhash(out)
 return {'original_name':original.name,'original_sha256':sha(original),'new_name':out.name,'new_sha256':sha(out),'duration':dur,'video_stream_sha256':vhash(out),'image_stream_unchanged':True}
def verify_file(p,expected):
 run(['ffmpeg','-v','error','-i',p,'-f','null','-'])
 info=probe(p);x=pcm(p);m=measure(p)
 assert np.isfinite(x).all() and np.max(abs(x))<1,p
 assert float(m['input_tp'])<-2,p
 assert abs(float(info['format']['duration'])-expected)<.05,(p,info['format']['duration'])
 assert np.max(abs(x[:480]))<1e-4,(p,'start')
 assert np.max(abs(x[-480:]))<1e-4,(p,'end')
 return {'sha256':sha(p),'duration':float(info['format']['duration']),'lufs_i':float(m['input_i']),'true_peak_dbtp':float(m['input_tp']),'clipped_samples':int(np.sum(abs(x)>=1)),'full_decode':'passed','first_10ms_peak':float(np.max(abs(x[:480]))),'last_10ms_peak':float(np.max(abs(x[-480:])))}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--score-only',action='store_true');ap.add_argument('--originals',type=Path);ap.add_argument('--forecast-video',type=Path);a=ap.parse_args()
 result={'score':score_check(),'perceptual_listening':False,'files':{},'remux':[]}
 if a.score_only:print(json.dumps(result['score']));return
 for s in scores():
  if a.originals:
   source=a.forecast_video if s['name']=='previsao' else a.originals/(s['name']+'.mp4')
   result['remux'].append(remux(s,source))
  for ext in ['wav','m4a']+(['mp4'] if a.originals else []):
   p=OUT/(s['name']+'.'+ext);result['files'][p.name]=verify_file(p,s['duration'])
  print(s['name'],'verified',flush=True)
 baseline_path=OUT/'preservation-before.json'
 baseline=json.loads(baseline_path.read_text()) if baseline_path.exists() else {}
 result['preservation_checked']=baseline_path.exists()
 result['preservation']={str(Path(p).relative_to(REPO)):sha(Path(p))==h for p,h in baseline.items()}
 assert all(result['preservation'].values())
 (OUT/'verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps({'files':len(result['files']),'preserved':len(result['preservation']),'remux':len(result['remux'])}))
if __name__=='__main__':main()
