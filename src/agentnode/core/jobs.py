from __future__ import annotations
import asyncio,json,time,uuid
from pathlib import Path
from typing import Awaitable,Callable,Any
from ..models import Job,JobState
class JobStore:
    def __init__(self,path:str|Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.jobs={}; self.tasks={} ; self.load()
    def load(self):
        if self.path.exists():
            for line in self.path.read_text('utf-8',errors='replace').splitlines():
                try: j=Job.model_validate_json(line); self.jobs[j.id]=j
                except Exception: pass
            for j in self.jobs.values():
                if j.state in {JobState.queued,JobState.running}: j.state=JobState.interrupted; j.message="node restarted"; j.updated_at=time.time()
    def _append(self,j:Job):
        with self.path.open('a',encoding='utf-8') as f:f.write(j.model_dump_json()+"\n")
    def create(self,kind,owner,input,trace_id=None,target_node=None):
        t=time.time(); j=Job(id=uuid.uuid4().hex,kind=kind,owner=owner,input=input,trace_id=trace_id,target_node=target_node,created_at=t,updated_at=t); self.jobs[j.id]=j; self._append(j); return j
    def update(self,j:Job,**kw):
        for k,v in kw.items(): setattr(j,k,v)
        j.updated_at=time.time(); self._append(j); return j
    async def run(self,j:Job,fn:Callable[[Job],Awaitable[Any]]):
        self.update(j,state=JobState.running,phase="running",progress=max(j.progress,1))
        try:
            r=await fn(j); self.update(j,state=JobState.succeeded,phase="done",progress=100,result=r); return r
        except asyncio.CancelledError:
            self.update(j,state=JobState.cancelled,phase="cancelled",message="cancelled"); raise
        except Exception as e:
            self.update(j,state=JobState.failed,phase="failed",error=f"{type(e).__name__}: {e}"); return None
    def submit(self,j,fn): self.tasks[j.id]=asyncio.create_task(self.run(j,fn)); return j
    def get(self,jid): return self.jobs.get(jid)
    def list(self,limit=100): return sorted(self.jobs.values(),key=lambda j:j.updated_at,reverse=True)[:limit]
    def cancel(self,jid):
        t=self.tasks.get(jid)
        if t and not t.done(): t.cancel(); return True
        return False
