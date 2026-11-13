"""Browser regression with real video decode and isolated mocked HTTP failures.
Runs the local working-tree player in a silent throwaway browser; no user profile.
"""
import asyncio,json,os,subprocess,tempfile,time
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
async def main():
 with tempfile.TemporaryDirectory(prefix='ktv-recovery-') as tmp:
  video=Path(tmp)/'clip.mp4'
  subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=320x180:r=10','-t','40','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],check=True)
  payload=video.read_bytes(); stamp=int(time.time()*1000)
  schedule={'format':2,'rev':'good','from':stamp-1000,'to':stamp+86400000,'blocks':{'toons':{'pt':'Desenhos'}},'ours':{},'titles':{'test':{'title':'Test programme','block':'toons','dur':40,'sources':[{'url':'https://fixture.test/clip.mp4','dur':40}]}},'items':[[stamp-1000,stamp+86400000,'test','toons']]}
  reserve={'format':1,'at':stamp,'items':[{'id':'reserve','title':'Reserve programme','block':'toons','dur':40,'copies':['https://fixture.test/clip.mp4']}]}
  async with async_playwright() as p:
   b=await p.chromium.launch(executable_path=os.environ.get('BROWSER_BIN','/Applications/Brave Browser.app/Contents/MacOS/Brave Browser'),headless=True,args=['--mute-audio'])
   try:
    for name in ['pointer','expired','no-grade','warm-cache','malformed','blocked-storage','no-reserve','dead-reserve']:
     stamp=int(time.time()*1000)
     schedule['from']=stamp-1000;schedule['to']=stamp+86400000
     schedule['items']=[[stamp-1000,stamp+86400000,'test','toons']]
     c=await b.new_context(viewport={'width':390,'height':844} if name=='expired' else {'width':1280,'height':800})
     mode={'value':'healthy' if name=='warm-cache' else name}
     if name=='blocked-storage':await c.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked storage')}})")
     async def route(r):
      path=r.request.url.split('fixture.test/',1)[-1].split('?')[0]
      if path=='grade/now.json':
       if mode['value'] in ['pointer','no-grade','offline','no-reserve','dead-reserve']:return await r.abort()
       return await r.fulfill(json={'generated':stamp,'rev2':'good','schedule2':'schedule2.json'})
      if path.startswith('grade/schedule'):
       if mode['value'] in ['no-grade','offline','no-reserve','dead-reserve']:return await r.abort()
       data=json.loads(json.dumps(schedule))
       if mode['value']=='expired':
        data['from']-=10*86400000;data['to']-=10*86400000
        for i in data['items']:i[0]-=10*86400000;i[1]-=10*86400000
       if mode['value']=='malformed':data['items']=[None]
       return await r.fulfill(json=data)
      if path=='tv/reserva.json':
       if mode['value']=='no-reserve':return await r.abort()
       return await r.fulfill(json=reserve)
      if path=='tv/tecnicos.mp4':return await r.fulfill(status=200,content_type='video/mp4',body=payload)
      if path=='clip.mp4' and mode['value']=='dead-reserve':return await r.abort()
      if path=='clip.mp4':return await r.fulfill(status=200,content_type='video/mp4',body=payload,headers={'accept-ranges':'bytes'})
      if path=='tv/tv.js':return await r.fulfill(path=str(ROOT/'public/tv/tv.js'),content_type='application/javascript')
      if path=='':return await r.fulfill(content_type='text/html',body='<div id="ktv"></div><div id="ktv-info"></div><script src="tv/tv.js"></script>')
      return await r.fulfill(status=404,body='missing')
     await c.route('**/*',route)
     page=await c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
     await page.goto('https://fixture.test/')
     if name=='warm-cache':
      await page.wait_for_function('window.KTV?.S?.rev === "good"');mode['value']='offline';await page.reload()
     await page.locator('.ktv-power').click()
     try:
      await page.wait_for_function("[...document.querySelectorAll('video.air')].some(v=>!v.paused && v.currentTime>0.5)",timeout=45000)
      assert not errors,errors
      if name in ["pointer","warm-cache","blocked-storage"]:
       assert await page.evaluate("window.KTV.S.rev === 'good' && !document.querySelector('#ktv').classList.contains('ktv-alt')")
      # Return from emergency to the live schedule without reload; online event is the trigger.
      if name in ['expired','no-grade','malformed','no-reserve','dead-reserve']:
       mode['value']='healthy';await page.evaluate("window.dispatchEvent(new Event('online'))")
       await page.wait_for_function('window.KTV?.S?.rev === "good" && window.KTV.S.to>Date.now()',timeout=12000)
       await page.wait_for_function("!document.querySelector('#ktv').classList.contains('ktv-alt')",timeout=12000)
      await page.locator('[data-k=power]').click()
      await page.wait_for_timeout(500)
      assert await page.evaluate("[...document.querySelectorAll('video')].every(v=>v.paused)")
      print('PASS',name,flush=True)
     except Exception:
      print('FAIL',name,'page errors',errors,flush=True);raise
     finally:await c.close()
   finally:await b.close()
if __name__=='__main__':asyncio.run(main())
