from __future__ import annotations
import asyncio,os,signal,time
from pathlib import Path
from .config import AppConfig
from .policy import check_shell
from ..models import Principal,Job,ShellRequest
from ..platform import get_platform_adapter
class ShellRunner:
    def __init__(self,cfg:AppConfig): self.cfg=cfg; self.platform=get_platform_adapter(); self._procs={}
    async def execute(self,req:ShellRequest,p:Principal,job:Job|None=None):
        check_shell(self.cfg,p,req.command,req.super_mode,delegated=bool(req.hops) or req.trace_id is not None); spec=self.platform.shell(req.command,req.shell); started=time.time()
        proc=await asyncio.create_subprocess_exec(*spec.argv,cwd=req.cwd or None,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,creationflags=spec.creationflags,start_new_session=spec.start_new_session)
        if job: self._procs[job.id]=proc
        try:
            out,err=await asyncio.wait_for(proc.communicate(),timeout=min(req.timeout_s,3600))
        except asyncio.TimeoutError:
            await self.kill(proc); raise TimeoutError(f"command exceeded {req.timeout_s}s")
        finally:
            if job:self._procs.pop(job.id,None)
        lim=self.cfg.shell.output_limit
        return {"exit_code":proc.returncode,"stdout":out[:lim].decode(errors='replace'),"stderr":err[:lim].decode(errors='replace'),"duration_ms":int((time.time()-started)*1000),"truncated":len(out)>lim or len(err)>lim}
    async def kill(self,proc):
        if proc.returncode is not None:return
        try:
            if os.name=="nt":
                killer=await asyncio.create_subprocess_exec("taskkill","/PID",str(proc.pid),"/T","/F",stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL); await killer.wait()
            else: os.killpg(proc.pid,signal.SIGKILL)
        except Exception:
            try: proc.kill()
            except ProcessLookupError: pass
