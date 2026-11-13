#!/usr/bin/env python3
"""Read-only public delivery verification; nonzero exit means one actionable incident.
No AI, credentials, camera, browser profile or mutable runtime required.
"""
import argparse, json, time, urllib.request

def validate(s, n, now):
    errors=[]
    if not isinstance(s,dict) or not isinstance(n,dict): return ['invalid schedule or pointer']
    rows=s.get('items')
    if not isinstance(rows,list) or not rows: return ['empty programme schedule']
    start,end=s.get('from'),s.get('to')
    if not isinstance(start,(int,float)) or not isinstance(end,(int,float)): return ['invalid schedule bounds']
    if end<=now: errors.append('schedule expired')
    elif end-now<24*3600000: errors.append('schedule reserve below 24 hours')
    if start>now: errors.append('schedule starts in the future')
    if s.get('rev') != n.get('rev2',n.get('rev')): errors.append('schedule revision differs from public pointer')
    generated=n.get('generated')
    if not isinstance(generated,(int,float)) or now-generated>12*3600000: errors.append('publication is stale (over 12 hours)')
    if isinstance(generated,(int,float)) and generated>now+5*60000: errors.append('publication timestamp is in the future')
    known=set(s.get('titles',{}))|set(s.get('ours',{}));cursor=start
    for row in rows:
        if not isinstance(row,list) or len(row)<4 or not all(isinstance(x,(int,float)) for x in row[:2]):
            errors.append('invalid schedule row');break
        if row[0]!=cursor or row[1]<=row[0]: errors.append('schedule gap or overlap');break
        if row[2] not in known: errors.append('unknown programme reference');break
        cursor=row[1]
    if cursor!=end: errors.append('schedule end differs from its final programme')
    return errors

def get_json(base,path):
    with urllib.request.urlopen(base+path,timeout=20) as r:return json.load(r)

def check(base):
    errors=[];now=int(time.time()*1000);s={};n={}
    try:
        n=get_json(base,'grade/now.json?monitor='+str(now))
        s=get_json(base,'grade/schedule2.json?monitor='+str(now))
        errors+=validate(s,n,now)
        reserve=get_json(base,'tv/reserva.json?monitor='+str(now))
        if not isinstance(reserve.get('items'),list) or not reserve['items']:errors.append('no reserve programmes')
        # Verify a local approved fallback is actually available, not just a JSON pointer.
        req=urllib.request.Request(base+'tv/tecnicos.mp4',headers={'Range':'bytes=0-1023'})
        with urllib.request.urlopen(req,timeout=20) as r:
            data=r.read(1024)
            if len(data)<32 or b'ftyp' not in data[:64]:errors.append('local fallback video is not an MP4')
    except Exception as exc:errors.append(type(exc).__name__+': '+str(exc))
    return {'ok':not errors,'checked':now,'errors':errors,'generated':n.get('generated'),'schedule_rev':s.get('rev'),'schedule_until':s.get('to')}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',default='https://tv.kolja.com.br/');ap.add_argument('--attempts',type=int,default=1);ap.add_argument('--delay',type=int,default=30);ap.add_argument('--out');a=ap.parse_args()
    result=None
    attempts=max(1,min(a.attempts,6))
    for attempt in range(attempts):
        result=check(a.base.rstrip('/')+'/')
        if result['ok']:break
        if attempt+1<attempts:time.sleep(max(0,min(a.delay,60)))
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if a.out:
        with open(a.out,'w') as f:f.write(text+'\n')
    print(text);return 0 if result['ok'] else 1
if __name__=='__main__':raise SystemExit(main())
