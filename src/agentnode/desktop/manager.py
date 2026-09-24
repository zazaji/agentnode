from __future__ import annotations
import platform
from multiprocessing.connection import Client
from .local import LocalDesktopBackend
from ..core.auth import require

class DesktopManager:
    def __init__(self,cfg):
        self.cfg=cfg; self.local=LocalDesktopBackend(cfg)
    def _use_worker(self):
        return platform.system()=='Windows' and self.cfg.desktop.use_worker_on_windows
    def _worker(self,req):
        try:
            c=Client(self.cfg.desktop.worker_pipe,family='AF_PIPE',authkey=self.cfg.desktop.worker_secret.encode())
            c.send(req); res=c.recv(); c.close(); return res
        except Exception as e:
            # In dev/manual mode fall back locally. In a SYSTEM service this will normally report Session 0 limitations.
            res=self._local(req)
            if isinstance(res,dict): res.setdefault('_worker_warning',f'worker unavailable: {e}')
            return res
    def _local(self,req):
        op=req['op']
        if op=='observe': return self.local.observe(req.get('include_image',True),req.get('ocr',False))
        if op=='tree': return self.local.tree(req.get('title_re','.*'))
        if op=='act':
            from ..models import DesktopAct
            return self.local.act(DesktopAct.model_validate(req['action']))
        if op=='native_windows': return self.local.native_windows()
        if op=='window_control': return self.local.window_control(req['hwnd'],req['action'],x=req.get('x'),y=req.get('y'),w=req.get('w'),h=req.get('h'))
        if op=='uia_find': return self.local.uia_find(req.get('title_re','.*'),req.get('name'),req.get('control_type'))
        if op=='uia_invoke': return self.local.uia_invoke(req.get('title_re','.*'),req.get('name'),req.get('automation_id'))
        return {'error':'unknown desktop operation'}
    def _call(self,req): return self._worker(req) if self._use_worker() else self._local(req)
    def observe(self,p,include_image=True,ocr=False): require(p,'desktop.observe'); return self._call({'op':'observe','include_image':include_image,'ocr':ocr})
    def tree(self,p,title_re='.*'): require(p,'desktop.observe'); return self._call({'op':'tree','title_re':title_re})
    def act(self,p,a): require(p,'desktop.input'); return self._call({'op':'act','action':a.model_dump()})

    def native_windows(self,p): require(p,"desktop.observe"); return self._call({"op":"native_windows"})
    def window_control(self,p,hwnd,action,**kw): require(p,"desktop.input"); return self._call({"op":"window_control","hwnd":hwnd,"action":action,**kw})
    def uia_find(self,p,title_re=".*",name=None,control_type=None): require(p,"desktop.observe"); return self._call({"op":"uia_find","title_re":title_re,"name":name,"control_type":control_type})
    def uia_invoke(self,p,title_re=".*",name=None,automation_id=None): require(p,"desktop.input"); return self._call({"op":"uia_invoke","title_re":title_re,"name":name,"automation_id":automation_id})
