from __future__ import annotations
import asyncio, os, re, signal, time, uuid
from collections import deque
from dataclasses import dataclass, field
from ..platform import get_platform_adapter

_PROMPT_RE=re.compile(r"(?:^|\n)(?:[^\n]{0,100})?(?:>>>|\$|#|>|:\s*)\s*$")

@dataclass
class TerminalSession:
    id: str; owner: str; command: str; process: asyncio.subprocess.Process; created_at: float; interactive: bool
    buffer: deque[tuple[int,str,str]] = field(default_factory=lambda: deque(maxlen=8000))
    cursor: int = 0; evicted: int = 0; closed: bool = False; last_output_at: float|None=None; first_output_at: float|None=None
    shell: str|None=None; cwd: str|None=None

class TerminalManager:
    def __init__(self): self.sessions={}; self.platform=get_platform_adapter()

    @staticmethod
    def _env():
        env=dict(os.environ); env.setdefault("TERM","xterm-256color")
        if os.name=="nt":
            # Some launchers inherit a broken PATHEXT. Repair the normal executable extensions.
            ext=[x for x in env.get("PATHEXT","").split(";") if x]
            required=[".COM",".EXE",".BAT",".CMD"]
            for x in required:
                if x.lower() not in {e.lower() for e in ext}: ext.append(x)
            env["PATHEXT"]=";".join(ext)
        return env

    async def start(self, owner, command, shell=None, cwd=None, interactive=False):
        spec=self.platform.shell(command,shell)
        proc=await asyncio.create_subprocess_exec(*spec.argv,cwd=cwd or None,env=self._env(),
            stdin=asyncio.subprocess.PIPE if interactive else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,
            creationflags=spec.creationflags,start_new_session=spec.start_new_session)
        sid=uuid.uuid4().hex; sess=TerminalSession(sid,owner,command,proc,time.time(),interactive,shell=shell,cwd=cwd)
        self.sessions[sid]=sess
        asyncio.create_task(self._pump(sess,proc.stdout,"stdout")); asyncio.create_task(self._pump(sess,proc.stderr,"stderr")); asyncio.create_task(self._wait(sess))
        return sess

    async def _pump(self,sess,stream,source):
        if not stream:return
        while True:
            raw=await stream.readline()
            if not raw:break
            now=time.time(); sess.first_output_at=sess.first_output_at or now; sess.last_output_at=now
            if len(sess.buffer)==sess.buffer.maxlen:sess.evicted+=1
            sess.cursor+=1; sess.buffer.append((sess.cursor,source,raw.decode(errors="replace").rstrip("\n")))

    async def _wait(self,sess):
        await sess.process.wait(); sess.closed=True

    def _check(self,sid,owner):
        sess=self.sessions.get(sid)
        if not sess or sess.owner!=owner: raise PermissionError("session not found or owner mismatch")
        return sess

    def read(self,sid,owner,cursor=0,limit=200):
        sess=self._check(sid,owner); limit=min(max(limit,1),2000); items=list(sess.buffer)
        chunk=[x for x in items if x[0]>cursor][:limit] if cursor else items[-limit:]
        text="\n".join(x[2] for x in chunk[-12:]); waiting=bool(sess.interactive and not sess.closed and _PROMPT_RE.search(text))
        return {"session_id":sid,"cursor":sess.cursor,
            "events":[{"cursor":c,"source":src,"text":txt} for c,src,txt in chunk],
            "lines":[txt for _,_,txt in chunk],"closed":sess.closed,"returncode":sess.process.returncode,
            "waiting_for_input":waiting,"interactive":sess.interactive,"pid":sess.process.pid,
            "evicted_lines":sess.evicted,"created_at":sess.created_at,"first_output_at":sess.first_output_at,"last_output_at":sess.last_output_at}

    def list(self,owner):
        return [{"session_id":s.id,"pid":s.process.pid,"command":s.command,"interactive":s.interactive,"closed":s.closed,
                 "returncode":s.process.returncode,"cursor":s.cursor,"evicted_lines":s.evicted,"created_at":s.created_at,"cwd":s.cwd,"shell":s.shell}
                for s in self.sessions.values() if s.owner==owner]

    async def write(self,sid,owner,data):
        sess=self._check(sid,owner)
        if not sess.interactive or not sess.process.stdin: raise PermissionError("interactive session required")
        sess.process.stdin.write(data.encode()); await sess.process.stdin.drain(); return {"ok":True}

    async def close(self,sid,owner):
        sess=self._check(sid,owner)
        if sess.process.returncode is None:
            try:
                if os.name=="nt":
                    killer=await asyncio.create_subprocess_exec("taskkill","/PID",str(sess.process.pid),"/T","/F",stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL); await killer.wait()
                else: os.killpg(sess.process.pid,signal.SIGTERM)
            except Exception:
                try:sess.process.terminate()
                except Exception:pass
        sess.closed=True; return {"ok":True}
