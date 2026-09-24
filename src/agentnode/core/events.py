from __future__ import annotations
import json,time
from pathlib import Path
class EventStore:
    def __init__(self,dir): self.dir=Path(dir); self.dir.mkdir(parents=True,exist_ok=True)
    def emit(self,job_id,kind,data):
        rec={"ts":time.time(),"kind":kind,"data":data}
        with (self.dir/f"{job_id}.jsonl").open('a',encoding='utf-8') as f:f.write(json.dumps(rec,ensure_ascii=False,default=str)+"\n")
    def read(self,job_id,cursor=0,limit=500):
        p=self.dir/f"{job_id}.jsonl"; lines=p.read_text('utf-8',errors='replace').splitlines() if p.exists() else []; chunk=lines[cursor:cursor+limit]
        return {"cursor":cursor+len(chunk),"events":[json.loads(x) for x in chunk],"more":cursor+len(chunk)<len(lines)}
