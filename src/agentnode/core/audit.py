from __future__ import annotations
import json,time,threading
from pathlib import Path
from typing import Any
class AuditLog:
    def __init__(self,path:str|Path): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.lock=threading.Lock()
    def emit(self,event:str,principal:str,details:dict[str,Any]):
        rec={"ts":time.time(),"event":event,"principal":principal,"details":details}
        with self.lock:
            with self.path.open('a',encoding='utf-8') as f: f.write(json.dumps(rec,ensure_ascii=False,default=str)+"\n")
    def tail(self,n:int=200):
        if not self.path.exists(): return []
        lines=self.path.read_text('utf-8',errors='replace').splitlines()[-n:]
        return [json.loads(x) for x in lines if x.strip()]
