from __future__ import annotations
import asyncio,json,os,shutil
from pathlib import Path
class AgentRuntimeManager:
    def __init__(self,cfg,events): self.cfg=cfg; self.events=events
    def available(self):
        out={}
        for name,c in self.cfg.agent.runtimes.items(): out[name]={"enabled":bool(c.get('enabled')),"executable":c.get('executable'),"found":bool(shutil.which(c.get('executable','')) or Path(c.get('executable','')).exists())}
        return out
    async def run(self,job,prompt,cwd=None,runtime=None,timeout_s=1800):
        name=runtime or self.cfg.agent.default_runtime; c=self.cfg.agent.runtimes.get(name,{})
        if not c.get('enabled'): raise RuntimeError(f"runtime disabled: {name}")
        exe=c.get('executable',name)
        resolved=shutil.which(exe) or (str(exe) if Path(exe).exists() else None)
        if resolved: exe=resolved
        if name=='pi': return await self._run_pi(job,exe,prompt,cwd,timeout_s,c)
        return await self._run_generic(job,exe,prompt,cwd,timeout_s,c)
    async def _run_generic(self,job,exe,prompt,cwd,timeout_s,c):
        args=[exe]+list(c.get('args',[]))+[prompt]
        proc=await asyncio.create_subprocess_exec(*args,cwd=cwd or None,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        out,err=await asyncio.wait_for(proc.communicate(),timeout=timeout_s); self.events.emit(job.id,'agent.output',{'stdout':out.decode(errors='replace'),'stderr':err.decode(errors='replace')})
        if proc.returncode: raise RuntimeError(err.decode(errors='replace') or f"exit {proc.returncode}")
        return {'runtime':c,'exit_code':proc.returncode,'stdout':out.decode(errors='replace')}
    async def _run_pi(self,job,exe,prompt,cwd,timeout_s,c):
        env=os.environ.copy(); env.update({str(k):str(v) for k,v in c.get('env',{}).items()})
        args=[exe,'--mode','rpc']+list(c.get('args',[]))
        proc=await asyncio.create_subprocess_exec(*args,cwd=cwd or None,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,env=env)
        proc.stdin.write((json.dumps({'type':'prompt','message':prompt})+'\n').encode()); await proc.stdin.drain()
        collected=[]
        async def loop():
            while True:
                line=await proc.stdout.readline()
                if not line: break
                s=line.decode(errors='replace').rstrip(); collected.append(s)
                try: evt=json.loads(s)
                except Exception: evt={'raw':s}
                self.events.emit(job.id,'agent.rpc',evt)
                if isinstance(evt,dict) and evt.get('type')=='agent_settled': break
        await asyncio.wait_for(loop(),timeout=timeout_s)
        if proc.returncode is None: proc.terminate()
        return {'runtime':'pi','events':len(collected),'last':collected[-1] if collected else None}
