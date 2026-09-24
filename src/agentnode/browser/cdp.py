from __future__ import annotations
import asyncio, base64, ipaddress, json
from typing import Any
from urllib.parse import urlparse, quote
import httpx
from ..core.auth import require

class CDPManager:
    """Small CDP adapter.

    The authenticated AgentNode boundary talks to a Chrome/Edge remote-debugging
    endpoint. The debugging endpoint should normally remain on loopback.
    """
    def __init__(self,cfg):
        self.cfg=cfg

    @property
    def base(self):
        return self.cfg.browser.cdp_url.rstrip('/')

    def _check(self,p,write=False):
        require(p,'browser.write' if write else 'browser.read')
        if not self.cfg.browser.enabled:
            raise RuntimeError('browser CDP is disabled in config')
        parsed=urlparse(self.base); host=parsed.hostname or ''
        if not self.cfg.browser.allow_remote:
            try: loopback=ipaddress.ip_address(host).is_loopback
            except ValueError: loopback=host.lower() in {'localhost'}
            if not loopback:
                raise RuntimeError('remote CDP endpoint rejected; set browser.allow_remote=true explicitly')

    async def status(self,p):
        self._check(p)
        async with httpx.AsyncClient(timeout=self.cfg.browser.timeout_s) as c:
            r=await c.get(self.base+'/json/version'); r.raise_for_status(); return r.json()

    async def tabs(self,p):
        self._check(p)
        async with httpx.AsyncClient(timeout=self.cfg.browser.timeout_s) as c:
            r=await c.get(self.base+'/json'); r.raise_for_status(); return r.json()

    async def _target(self,p,target_id:str):
        tabs=await self.tabs(p)
        t=next((x for x in tabs if x.get('id')==target_id),None)
        if not t or not t.get('webSocketDebuggerUrl'): raise KeyError('target not found')
        return t

    def _ws_sync(self,url:str,method:str,params:dict[str,Any]|None=None):
        try: import websocket
        except ImportError as e: raise RuntimeError('websocket-client required; install agentnode[browser]') from e
        # Chrome 111+ rejects CDP websocket handshakes that carry an Origin header
        # (DNS-rebinding protection); DevTools protocol clients omit it.
        ws=websocket.create_connection(url,timeout=self.cfg.browser.timeout_s,suppress_origin=True)
        try:
            msg_id=1; ws.send(json.dumps({'id':msg_id,'method':method,'params':params or {}}))
            while True:
                obj=json.loads(ws.recv())
                if obj.get('id')==msg_id:
                    if 'error' in obj: raise RuntimeError(str(obj['error']))
                    return obj.get('result',{})
        finally: ws.close()

    async def _ws(self,url:str,method:str,params:dict[str,Any]|None=None):
        return await asyncio.to_thread(self._ws_sync,url,method,params)

    async def command(self,p,target_id:str,method:str,params:dict[str,Any]|None=None,write:bool=False):
        self._check(p,write=write); t=await self._target(p,target_id)
        return await self._ws(t['webSocketDebuggerUrl'],method,params)

    async def evaluate(self,p,target_id:str,expression:str):
        result=await self.command(p,target_id,'Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True},write=True)
        raw=json.dumps(result,default=str)
        if len(raw)>self.cfg.browser.max_snapshot_chars:
            return {'truncated':True,'chars':len(raw),'preview':raw[:self.cfg.browser.max_snapshot_chars]}
        return result

    async def navigate(self,p,target_id:str,url:str):
        return await self.command(p,target_id,'Page.navigate',{'url':url},write=True)

    async def snapshot(self,p,target_id:str):
        self._check(p); expr='({url:location.href,title:document.title,text:document.body?document.body.innerText:"",html:document.documentElement?document.documentElement.outerHTML:""})'
        result=await self.command(p,target_id,'Runtime.evaluate',{'expression':expr,'returnByValue':True},write=False)
        value=(result.get('result') or {}).get('value') or result
        if isinstance(value,dict):
            out={}
            for k,v in value.items():
                if isinstance(v,str) and len(v)>self.cfg.browser.max_snapshot_chars:
                    out[k]=v[:self.cfg.browser.max_snapshot_chars]; out[k+'_truncated']=True; out[k+'_chars']=len(v)
                else: out[k]=v
            return out
        return value

    async def screenshot(self,p,target_id:str,format:str='png',quality:int=90):
        self._check(p)
        params={'format':format,'fromSurface':True}
        if format=='jpeg': params['quality']=max(0,min(100,quality))
        result=await self.command(p,target_id,'Page.captureScreenshot',params,write=False)
        data=result.get('data',''); approx=(len(data)*3)//4
        if approx>self.cfg.browser.max_screenshot_bytes:
            return {'target_id':target_id,'format':format,'bytes':approx,'base64':'','truncated':True,'error':'screenshot exceeds max_screenshot_bytes'}
        return {'target_id':target_id,'format':format,'bytes':approx,'base64':data,'truncated':False}

    async def click(self,p,target_id:str,selector:str):
        q=json.dumps(selector)
        expr=f'''(()=>{{const e=document.querySelector({q});if(!e)return {{ok:false,error:"selector not found"}};e.scrollIntoView({{block:"center",inline:"center"}});e.click();return {{ok:true,tag:e.tagName,text:(e.innerText||e.value||"").slice(0,300)}};}})()'''
        result=await self.evaluate(p,target_id,expr)
        return (result.get('result') or {}).get('value') or result

    async def type_text(self,p,target_id:str,selector:str,text:str,clear:bool=True):
        q=json.dumps(selector); v=json.dumps(text); clear_js='e.value="";' if clear else ''
        expr=f'''(()=>{{const e=document.querySelector({q});if(!e)return {{ok:false,error:"selector not found"}};e.focus();{clear_js}e.value=e.value+{v};e.dispatchEvent(new Event("input",{{bubbles:true}}));e.dispatchEvent(new Event("change",{{bubbles:true}}));return {{ok:true,value:e.value}};}})()'''
        result=await self.evaluate(p,target_id,expr)
        return (result.get('result') or {}).get('value') or result

    async def new_tab(self,p,url:str='about:blank'):
        self._check(p,write=True)
        async with httpx.AsyncClient(timeout=self.cfg.browser.timeout_s) as c:
            r=await c.put(self.base+'/json/new?'+quote(url,safe=':/?=&%')); r.raise_for_status(); return r.json()

    async def close_tab(self,p,target_id:str):
        self._check(p,write=True)
        async with httpx.AsyncClient(timeout=self.cfg.browser.timeout_s) as c:
            r=await c.get(self.base+'/json/close/'+quote(target_id,safe='')); r.raise_for_status(); return {'ok':True,'target_id':target_id,'response':r.text}
