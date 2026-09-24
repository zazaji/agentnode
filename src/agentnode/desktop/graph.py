from __future__ import annotations
import time, hashlib, json
from ..core.auth import require


def _norm_bounds(v):
    if not isinstance(v,(list,tuple)) or len(v)!=4: return None
    try:
        x1,y1,x2,y2=[float(x) for x in v]
        if x2<x1: x1,x2=x2,x1
        if y2<y1: y1,y2=y2,y1
        return [x1,y1,x2,y2]
    except Exception:return None


def _overlap_ratio(a,b):
    a=_norm_bounds(a); b=_norm_bounds(b)
    if not a or not b:return 0.0
    x1=max(a[0],b[0]); y1=max(a[1],b[1]); x2=min(a[2],b[2]); y2=min(a[3],b[3])
    inter=max(0,x2-x1)*max(0,y2-y1)
    if inter<=0:return 0.0
    area_b=max(1,(b[2]-b[0])*(b[3]-b[1]))
    return inter/area_b


class DesktopGraph:
    """Fuse structured and visual desktop observations into a stable graph."""
    def __init__(self,desktop): self.desktop=desktop

    def build(self,p,title_re='.*',include_ocr=False):
        require(p,'desktop.observe')
        wins=self.desktop.native_windows(p) or []
        tree=self.desktop.tree(p,title_re)
        obs=self.desktop.observe(p,include_image=False,ocr=include_ocr)
        nodes=[]; edges=[]; window_by_handle={}
        for i,w in enumerate(wins):
            wid=f"window:{w.get('hwnd',i)}"; node={'id':wid,'kind':'window',**w}; nodes.append(node)
            if w.get('hwnd'): window_by_handle[int(w['hwnd'])]=wid

        uia_nodes=[]
        def walk(obj,parent=None):
            if not isinstance(obj,dict): return
            raw=f"{obj.get('handle')}|{obj.get('automation_id')}|{obj.get('name')}|{obj.get('type')}|{obj.get('bounds')}"
            nid='uia:'+hashlib.sha1(raw.encode()).hexdigest()[:16]
            node={'id':nid,'kind':'uia','name':obj.get('name'),'control_type':obj.get('type'),'automation_id':obj.get('automation_id'),'handle':obj.get('handle'),'bounds':obj.get('bounds')}
            nodes.append(node); uia_nodes.append(node)
            if parent: edges.append({'from':parent,'to':nid,'type':'contains'})
            h=obj.get('handle')
            if h:
                try:
                    if int(h) in window_by_handle: edges.append({'from':window_by_handle[int(h)],'to':nid,'type':'native_identity'})
                except Exception: pass
            for c in obj.get('children',[]) or []: walk(c,nid)
        walk(tree)

        ocr_nodes=[]
        if include_ocr and isinstance(obs,dict):
            ocr=obs.get('ocr') or {}
            items=ocr.get('items',[]) if isinstance(ocr,dict) else (ocr if isinstance(ocr,list) else [])
            for idx,item in enumerate(items or []):
                box=item.get('box') or []; flat=[]
                for pt in box:
                    if isinstance(pt,(list,tuple)) and len(pt)>=2: flat.extend([pt[0],pt[1]])
                bounds=None
                if flat:
                    xs=flat[0::2]; ys=flat[1::2]; bounds=[min(xs),min(ys),max(xs),max(ys)]
                node={'id':f'ocr:{idx}','kind':'ocr','text':item.get('text'),'confidence':item.get('confidence'),'bounds':bounds}
                nodes.append(node); ocr_nodes.append(node)

        # Link OCR to the most specific UIA element that spatially contains it.
        for o in ocr_nodes:
            candidates=[]
            for u in uia_nodes:
                score=_overlap_ratio(u.get('bounds'),o.get('bounds'))
                if score>=0.6:
                    b=_norm_bounds(u.get('bounds')); area=(b[2]-b[0])*(b[3]-b[1]) if b else 1e30
                    candidates.append((area,-score,u['id'],score))
            if candidates:
                _,_,uid,score=min(candidates)
                edges.append({'from':uid,'to':o['id'],'type':'text_evidence','score':round(score,4)})

        payload={
            'generated_at':time.time(),'nodes':nodes,'edges':edges,
            'sources':{'windows':len(wins),'uia':len(uia_nodes),'ocr':len(ocr_nodes)},
            'observation':obs if include_ocr else {'capture':(obs or {}).get('capture') if isinstance(obs,dict) else None}
        }
        canonical={'nodes':nodes,'edges':edges,'sources':payload['sources']}
        payload['graph_hash']=hashlib.sha256(json.dumps(canonical,sort_keys=True,default=str).encode()).hexdigest()
        return payload
