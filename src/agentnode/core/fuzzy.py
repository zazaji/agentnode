from __future__ import annotations
from difflib import SequenceMatcher

def best_window(text: str, query: str) -> dict:
    """Find a close substring without third-party dependencies.

    Used only as a suggestion/dry-run helper unless explicitly enabled by caller.
    """
    if not query:
        return {"start":0,"end":0,"value":"","similarity":1.0}
    if query in text:
        i=text.index(query); return {"start":i,"end":i+len(query),"value":query,"similarity":1.0}
    qlen=len(query); best=(0.0,0,0,"")
    step=max(1, qlen//12)
    min_len=max(1,int(qlen*0.65)); max_len=min(len(text),int(qlen*1.35)+1)
    # coarse positions then local refinement around the best start
    for length in range(min_len,max_len+1,max(1,(max_len-min_len)//8 or 1)):
        for start in range(0,max(1,len(text)-length+1),step):
            val=text[start:start+length]; score=SequenceMatcher(None,val,query,autojunk=False).ratio()
            if score>best[0]: best=(score,start,start+length,val)
    _,bs,_,_=best
    for start in range(max(0,bs-step),min(len(text),bs+step+1)):
        for length in range(min_len,max_len+1):
            if start+length>len(text): break
            val=text[start:start+length]; score=SequenceMatcher(None,val,query,autojunk=False).ratio()
            if score>best[0]: best=(score,start,start+length,val)
    return {"start":best[1],"end":best[2],"value":best[3],"similarity":round(best[0],4)}
