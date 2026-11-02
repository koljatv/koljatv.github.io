"""Render approved originals offline; does not publish or touch source video/music."""
from pathlib import Path
import argparse, hashlib, json, math, struct, subprocess, sys
import numpy as np
from score import scores
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]
VENDOR=ROOT/'vendor'
ENGINE=VENDOR/'sfizz-1.2.3-macos/usr/local/bin/sfizz_render'
OUT=REPO/'media/trilhas-review/approved-v1'
SR=48000; PPQ=960; OFFSET=.08

def run(cmd): return subprocess.run([str(x) for x in cmd],capture_output=True,check=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pcm(p):return np.frombuffer(run(['ffmpeg','-v','error','-i',p,'-ac','2','-ar',SR,'-f','f32le','-']).stdout,np.float32).reshape(-1,2).copy()
def wav(p,x):
 subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i','pipe:0','-c:a','pcm_f32le',str(p)],input=np.asarray(x,np.float32).tobytes(),check=True)
def measure(p):
 t=run(['ffmpeg','-hide_banner','-i',p,'-af','loudnorm=I=-22:TP=-2:LRA=20:print_format=json','-f','null','-']).stderr.decode()
 return json.loads(t[t.rfind('{'):t.rfind('}')+1])
def vlq(n):
 a=[n&127]
 while n>>7:n>>=7;a.insert(0,(n&127)|128)
 return bytes(a)
def midi(s,role,dest):
 beat=60/s['bpm']; tick=lambda b:round((b+OFFSET/beat)*PPQ)
 events=[(0,0,b'\xff\x51\x03'+round(60000000/s['bpm']).to_bytes(3,'big')),(0,0,b'\xff\x58\x04\x04\x02\x18\x08'),(0,0,bytes([0xb0,7,100])),(0,0,bytes([0xb0,10,64]))]
 for b,d,n,v in s[role]:events.extend([(tick(b),2,bytes([0x90,n,v])),(tick(b+d),0,bytes([0x80,n,0]))])
 if role in s['expression']:
  points=s['expression'][role]
  for b in np.arange(0,s['duration']/beat,.1):
   v=round(float(np.interp(b,[p[0] for p in points],[p[1] for p in points])))
   events.append((tick(b),1,bytes([0xb0,11,v])))
 events.append((round(s['duration']/beat*PPQ),9,b'\xff\x2f\x00'))
 prev=0; data=b''
 for t,_,message in sorted(events):data+=vlq(t-prev)+message;prev=t
 dest.write_bytes(b'MThd'+struct.pack('>IHHH',6,0,1,PPQ)+b'MTrk'+struct.pack('>I',len(data))+data)

def synth(n,d,kind):
 t=np.arange(round(d*SR))/SR
 if kind=='bass':
  f=440*2**((n-69)/12)
  sig=sum(a*np.sin(2*np.pi*f*k*t) for k,a in [(1,1),(2,.32),(3,.16),(4,.05)])
  env=(1-np.exp(-t/.012))*np.exp(-t/.21)*np.minimum(1,np.maximum(0,(d-t)/.09))
 else:
  sig=np.sin(2*np.pi*1020*t+.38*np.sin(2*np.pi*1530*t))+.2*np.sin(2*np.pi*1780*t)
  env=(1-np.exp(-t/.004))*np.exp(-t/.022)*np.minimum(1,np.maximum(0,(d-t)/.025))
 return sig*env

def render(s):
 name=s['name']; dest=OUT/name; dest.mkdir(parents=True,exist_ok=True)
 (dest/'score.json').write_text(json.dumps(s,indent=2,ensure_ascii=False)+'\n')
 n=round(s['duration']*SR);beat=60/s['bpm'];stems={}
 for role,sfz in [('horn','FHornSus'),('strings','ViolaEnsSusVib')]:
  mid=dest/(role+'.mid');midi(s,role,mid)
  raw=dest/(role+'-sfizz.wav')
  run([ENGINE,'--sfz',VENDOR/(sfz+'.sfz'),'--midi',mid,'--wav',raw,'--samplerate',SR,'--quality',10])
  x=pcm(raw);stems[role]=np.pad(x,((0,max(0,n-len(x))),(0,0)))[:n]
 for role in ['bass','pulse']:
  midi(s,role,dest/(role+'.mid'));x=np.zeros((n,2))
  for b,d,p,v in s[role]:
   sig=synth(p,d*beat+.12,role)*v/100;start=round((OFFSET+b*beat)*SR);count=min(len(sig),n-start)
   x[start:start+count]+=sig[:count,None]
  stems[role]=x
 # Keep the preview's hierarchy; string-led pieces deliberately invert the two acoustic roles.
 targets={'horn':-25 if s['role']=='horn' else -31,'strings':-34.5 if s['role']=='horn' else -27,'bass':-33,'pulse':-42}
 eq={'horn':'highpass=f=135,lowpass=f=6800','strings':'highpass=f=185,lowpass=f=5400','bass':'highpass=f=35,lowpass=f=1500','pulse':'highpass=f=700,lowpass=f=2500'}
 mix=np.zeros((n,2)); stats={}
 for role,x in stems.items():
  raw=dest/(role+'-dry.wav');wav(raw,x);filtered=dest/(role+'-eq.wav')
  run(['ffmpeg','-v','error','-y','-i',raw,'-af',eq[role],'-c:a','pcm_f32le',filtered]);x=pcm(filtered)[:n]
  rms=math.sqrt(float(np.mean(x**2)));gain=10**(targets[role]/20)/max(rms,1e-9);x*=gain
  if name=='previsao':
   # Opening remains present, maps get a quieter bed, development returns briefly.
   t=np.arange(n)/SR
   curve={'horn':[1,1,.63,.63,.82,.7,.9,.68,.6,.73,.50],
          'strings':[1,1,.82,.82,.92,.86,.94,.82,.78,.9,.65],
          'bass':[1,1,.7,.7,.88,.7,.88,.7,.62,.72,.4],
          'pulse':[1,1,.65,.65,.8,.65,.8,.65,.55,.5,0]}[role]
   x*=np.interp(t,[0,8.8,10,27.5,29,47,49,58,64,69.6,72],curve)[:,None]
  if role=='strings':x[:,0]*=1.02;x[:,1]*=.98
  if role in ['horn','strings']:
   wet=np.zeros_like(x)
   for ch in range(2):
    seed=np.zeros(n)
    for delay,amp in [(.029,.31),(.047,.25),(.073,.19),(.113,.13),(.173,.07)]:
     k=round((delay+ch*.006)*SR);seed[k:]+=x[:-k,ch]*amp
    for delay in [.0113,.0179,.0237]:
     k=round((delay+ch*.0017)*SR);g=.61;y=-g*seed
     for rep in range(1,20):
      sh=k*rep
      if sh>=n:break
      y[sh:]+=(1-g*g)*g**(rep-1)*seed[:-sh]
     seed=y
    wet[:,ch]=seed
   x+=wet*(.23 if role=='horn' else .31)
  edge=np.ones(n);edge[:384]=np.sin(np.linspace(0,np.pi/2,384))**2
  tail=round(.6*SR);edge[-tail:]=np.cos(np.linspace(0,np.pi/2,tail))**2;x*=edge[:,None]
  wav(dest/(role+'.wav'),x);mix+=x
  stats[role]={'gain_db':20*math.log10(gain),'rms_dbfs':20*math.log10(max(math.sqrt(float(np.mean(x**2))),1e-12)),'peak_dbfs':20*math.log10(max(float(np.max(abs(x))),1e-12))}
 raw=dest/'mix-float.wav';wav(raw,mix);m=measure(raw)
 gain=min(s['lufs_target']-float(m['input_i']),-2.5-float(m['input_tp']))
 master=OUT/(name+'.wav');aac=OUT/(name+'.m4a')
 run(['ffmpeg','-v','error','-y','-i',raw,'-af',f'volume={gain}dB','-c:a','pcm_s24le',master])
 run(['ffmpeg','-v','error','-y','-i',master,'-c:a','aac','-b:a','192k','-movflags','+faststart',aac])
 (dest/'mastering.json').write_text(json.dumps({'raw':m,'linear_gain_db':gain,'limiter':False,'compressor':False,'stem_levels':stats},indent=2)+'\n')
 print(json.dumps({'name':name,'duration':s['duration'],'gain_db':round(gain,2),'aac_sha256':sha(aac)}),flush=True)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--only',nargs='*');a=ap.parse_args()
 OUT.mkdir(parents=True,exist_ok=True)
 for s in scores():
  if not a.only or s['name'] in a.only:render(s)
