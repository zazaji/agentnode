from __future__ import annotations
import asyncio, os, shutil, sys, tempfile, time
from pathlib import Path
from .auth import require
from ..models import Principal

class CodeExecutor:
    """Execute self-contained Python/Node/R snippets without shell quoting.

    This is equivalent in capability to arbitrary shell execution and therefore
    requires shell.write. It deliberately does not preserve interpreter state.
    """
    LANGS={
        "python":(["python","python3","py"],".py"),
        "node":(["node"],".mjs"),
        "javascript":(["node"],".mjs"),
        "r":(["Rscript"],".R"),
    }
    def _resolve_exe(self,candidates:list[str],fallback_sys:bool=False)->str|None:
        exe=next((shutil.which(x) for x in candidates if shutil.which(x)),None)
        if exe and os.name=="nt" and exe.casefold().endswith("windowsapps\\python.exe"):
            # The Microsoft Store python alias exits 9009 with no output when
            # launched from a service; prefer the py launcher or this runtime.
            exe=shutil.which("py") or (sys.executable if fallback_sys else None)
        # Windows services run with a stripped PATH (LocalSystem), so shutil.which
        # can miss an interpreter that is in fact this server's own runtime.
        if not exe and fallback_sys:
            exe=sys.executable
        return exe
    async def run(self,p:Principal,language:str,code:str,timeout_s:int=60,cwd:str|None=None):
        require(p,"shell.write")
        lang=language.lower()
        if lang not in self.LANGS: raise ValueError("language must be python, node/javascript, or r")
        candidates,suffix=self.LANGS[lang]; exe=self._resolve_exe(candidates,fallback_sys=(lang=="python"))
        if not exe: raise FileNotFoundError(f"runtime unavailable: {language}")
        fd,path=tempfile.mkstemp(prefix="agentnode-code-",suffix=suffix)
        started=time.time()
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as f:f.write(code)
            proc=await asyncio.create_subprocess_exec(exe,path,cwd=cwd or None,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            try: out,err=await asyncio.wait_for(proc.communicate(),timeout=min(max(timeout_s,1),3600))
            except asyncio.TimeoutError:
                proc.kill(); await proc.wait(); raise TimeoutError(f"code exceeded {timeout_s}s")
            return {"language":lang,"runtime":exe,"exit_code":proc.returncode,"stdout":out.decode(errors="replace"),"stderr":err.decode(errors="replace"),"duration_ms":int((time.time()-started)*1000)}
        finally:
            try: Path(path).unlink(missing_ok=True)
            except OSError: pass
