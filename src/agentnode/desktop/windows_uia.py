from __future__ import annotations
import platform,re
class WindowsUIA:
    def available(self): return platform.system()=="Windows"
    def _match(self,title_re:str):
        # Desktop().window(title_re=...) raises ElementAmbiguousError when several
        # top-level windows match; resolve deterministically to the first match.
        from pywinauto import Desktop
        pat=re.compile(title_re)
        for w in Desktop(backend='uia').windows():
            try: t=w.window_text() or ''
            except Exception: continue
            if pat.match(t): return w
        raise LookupError(f'no window matching {title_re!r}')
    def windows(self):
        if not self.available(): return []
        try:
            from pywinauto import Desktop
            out=[]
            for w in Desktop(backend='uia').windows():
                try:
                    r=w.rectangle(); out.append({"title":w.window_text(),"handle":int(w.handle),"bounds":[r.left,r.top,r.right,r.bottom],"control_type":w.element_info.control_type})
                except Exception: pass
            return out
        except Exception:return []
    def find(self,title_re='.*',name=None,control_type=None):
        if not self.available(): return []
        try:
            w=self._match(title_re); out=[]
            for e in w.descendants():
                try:
                    if name and e.window_text()!=name: continue
                    if control_type and e.element_info.control_type!=control_type: continue
                    r=e.rectangle(); out.append({'name':e.window_text(),'type':e.element_info.control_type,'automation_id':e.element_info.automation_id,'handle':int(getattr(e,'handle',0) or 0),'bounds':[r.left,r.top,r.right,r.bottom]})
                    if len(out)>=200: break
                except Exception: pass
            return out
        except Exception:return []
    def invoke(self,title_re='.*',name=None,automation_id=None):
        if not self.available(): return {'available':False,'reason':'Windows only'}
        try:
            w=self._match(title_re)
            ctrl=w.child_window(title=name,auto_id=automation_id) if (name or automation_id) else w
            obj=ctrl.wrapper_object();
            try: obj.invoke()
            except Exception: obj.click_input()
            return {'ok':True}
        except Exception as e:return {'ok':False,'error':str(e)}
    def tree(self,title_re=".*",max_depth=4):
        if not self.available(): return {"available":False,"reason":"Windows only"}
        try:
            w=self._match(title_re); root=w.wrapper_object()
            def walk(x,d):
                i=x.element_info; rec={"name":x.window_text(),"type":i.control_type,"automation_id":i.automation_id,"handle":int(getattr(x,'handle',0) or 0),"children":[]}
                if d<max_depth:
                    for c in x.children()[:200]:
                        try: rec['children'].append(walk(c,d+1))
                        except Exception: pass
                return rec
            return walk(root,0)
        except Exception as e:return {"available":False,"error":str(e)}
