from __future__ import annotations
import asyncio, json, re, shutil, time, uuid, zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET
from .files import FileManager
from ..models import Principal
from .auth import require

@dataclass
class SearchSession:
    id: str
    owner: str
    root: str
    pattern: str
    search_type: str
    created_at: float
    results: list[dict] = field(default_factory=list)
    complete: bool = False
    error: str | None = None
    task: asyncio.Task | None = None
    scanned: int = 0

class SearchManager:
    """Progressive file/content search with paging and cancellation."""
    def __init__(self, files: FileManager):
        self.files = files
        self.sessions: dict[str, SearchSession] = {}

    async def start(self, p: Principal, root: str, pattern: str, search_type: str = "content",
                    file_pattern: str | None = None, ignore_case: bool = True,
                    include_hidden: bool = False, max_results: int = 2000,
                    literal: bool = False) -> dict:
        require(p, "file.read")
        base = self.files._resolve(root)
        if search_type not in {"content", "files"}:
            raise ValueError("search_type must be content or files")
        sid = "search_" + uuid.uuid4().hex
        s = SearchSession(sid, p.name, str(base), pattern, search_type, time.time())
        self.sessions[sid] = s
        s.task = asyncio.create_task(self._run(s, base, pattern, search_type, file_pattern,
                                                ignore_case, include_hidden, max_results, literal))
        await asyncio.sleep(0.03)
        return self.read(sid, p.name, 0, 100)

    def _check(self, sid: str, owner: str) -> SearchSession:
        s = self.sessions.get(sid)
        if not s or s.owner != owner:
            raise KeyError("search session not found")
        return s

    async def _run(self, s: SearchSession, base: Path, pattern: str, search_type: str,
                   file_pattern: str | None, ignore_case: bool, include_hidden: bool,
                   max_results: int, literal: bool) -> None:
        try:
            if search_type == "files":
                await asyncio.to_thread(self._search_files, s, base, pattern, file_pattern,
                                        ignore_case, include_hidden, max_results, literal)
            else:
                await self._search_content(s, base, pattern, file_pattern, ignore_case,
                                           include_hidden, max_results, literal)
        except asyncio.CancelledError:
            s.error = "cancelled"
            raise
        except Exception as e:
            s.error = f"{type(e).__name__}: {e}"
        finally:
            s.complete = True

    def _search_files(self, s: SearchSession, base: Path, pattern: str, file_pattern: str | None,
                      ignore_case: bool, include_hidden: bool, max_results: int, literal: bool) -> None:
        flags = re.I if ignore_case else 0
        rx = re.compile(re.escape(pattern) if literal else pattern, flags)
        for f in base.rglob("*"):
            if len(s.results) >= max_results:
                break
            s.scanned += 1
            try:
                rel = str(f.relative_to(base))
                if not include_hidden and any(part.startswith(".") for part in f.relative_to(base).parts):
                    continue
                if file_pattern and not f.match(file_pattern):
                    continue
                if rx.search(f.name):
                    s.results.append({"type": "file", "path": str(f), "relative": rel})
            except OSError:
                continue

    async def _search_content(self, s: SearchSession, base: Path, pattern: str, file_pattern: str | None,
                              ignore_case: bool, include_hidden: bool, max_results: int, literal: bool) -> None:
        rg = shutil.which("rg")
        if rg:
            args = [rg, "--json", "--no-messages"]
            if ignore_case: args.append("-i")
            if include_hidden: args.append("--hidden")
            if literal: args.append("-F")
            if file_pattern: args += ["-g", file_pattern]
            args += [pattern, str(base)]
            proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.PIPE)
            assert proc.stdout
            async for raw in proc.stdout:
                if len(s.results) >= max_results:
                    proc.terminate(); break
                try:
                    j = json.loads(raw); d = j.get("data", {})
                    if j.get("type") == "match":
                        s.results.append({"type":"content", "path":d["path"]["text"],
                                          "line":d["line_number"], "text":d["lines"]["text"].rstrip()})
                except Exception:
                    pass
            await proc.wait()
        else:
            await asyncio.to_thread(self._fallback_content, s, base, pattern, file_pattern,
                                    ignore_case, include_hidden, max_results, literal)
        # Office formats need explicit extraction because rg sees ZIP containers.
        if len(s.results) < max_results:
            await asyncio.to_thread(self._office_content, s, base, pattern, file_pattern,
                                    ignore_case, include_hidden, max_results, literal)

    def _fallback_content(self, s: SearchSession, base: Path, pattern: str, file_pattern: str | None,
                          ignore_case: bool, include_hidden: bool, max_results: int, literal: bool) -> None:
        flags = re.I if ignore_case else 0
        rx = re.compile(re.escape(pattern) if literal else pattern, flags)
        for f in base.rglob(file_pattern or "*"):
            if len(s.results) >= max_results: break
            if not f.is_file() or f.suffix.lower() in {".docx", ".xlsx", ".xlsm", ".pdf"}: continue
            try:
                if not include_hidden and any(part.startswith(".") for part in f.relative_to(base).parts): continue
                if f.stat().st_size > 8_000_000: continue
                s.scanned += 1
                for i, line in enumerate(f.read_text("utf-8", errors="ignore").splitlines(), 1):
                    if rx.search(line):
                        s.results.append({"type":"content", "path":str(f), "line":i, "text":line[:2000]})
                        if len(s.results) >= max_results: break
            except OSError:
                pass

    def _office_content(self, s: SearchSession, base: Path, pattern: str, file_pattern: str | None,
                        ignore_case: bool, include_hidden: bool, max_results: int, literal: bool) -> None:
        flags = re.I if ignore_case else 0
        rx = re.compile(re.escape(pattern) if literal else pattern, flags)
        for f in base.rglob(file_pattern or "*"):
            if len(s.results) >= max_results: break
            if not f.is_file() or f.suffix.lower() not in {".docx", ".xlsx", ".xlsm"}: continue
            try:
                if not include_hidden and any(part.startswith(".") for part in f.relative_to(base).parts): continue
                lines = self._extract_ooxml_lines(f)
                for i, line in enumerate(lines, 1):
                    if rx.search(line):
                        s.results.append({"type":"content", "path":str(f), "line":i, "text":line[:2000], "container":"office"})
                        if len(s.results) >= max_results: break
            except Exception:
                pass

    @staticmethod
    def _extract_ooxml_lines(path: Path) -> list[str]:
        with zipfile.ZipFile(path) as z:
            if path.suffix.lower() == ".docx":
                root = ET.fromstring(z.read("word/document.xml"))
                ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                lines=[]
                for p in root.iter(ns+"p"):
                    text="".join((t.text or "") for t in p.iter(ns+"t"))
                    if text: lines.append(text)
                return lines
            # xlsx/xlsm: extract shared strings + inline/value cells as searchable text
            strings=[]
            if "xl/sharedStrings.xml" in z.namelist():
                r=ET.fromstring(z.read("xl/sharedStrings.xml"))
                strings=["".join(t.text or "" for t in si.iter() if t.tag.endswith("}t")) for si in r]
            lines=[]
            for name in sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")):
                r=ET.fromstring(z.read(name)); vals=[]
                for c in r.iter():
                    if not c.tag.endswith("}c"): continue
                    typ=c.attrib.get("t"); v=next((x.text for x in c if x.tag.endswith("}v")), None)
                    if v is None:
                        inline="".join(x.text or "" for x in c.iter() if x.tag.endswith("}t")); v=inline or None
                    if v is not None and typ=="s":
                        try: v=strings[int(v)]
                        except Exception: pass
                    if v is not None: vals.append(str(v))
                if vals: lines.append("\t".join(vals))
            return lines

    def read(self, sid: str, owner: str, offset: int = 0, length: int = 100) -> dict:
        s = self._check(sid, owner); offset=max(0,offset); length=min(max(1,length),1000)
        chunk=s.results[offset:offset+length]
        return {"session_id":sid,"results":chunk,"offset":offset,"returned":len(chunk),
                "total":len(s.results),"has_more":offset+len(chunk)<len(s.results),
                "complete":s.complete,"error":s.error,"scanned":s.scanned,
                "runtime_ms":int((time.time()-s.created_at)*1000)}

    def list(self, owner: str) -> list[dict]:
        return [{"session_id":s.id,"pattern":s.pattern,"root":s.root,"type":s.search_type,
                 "results":len(s.results),"complete":s.complete,"error":s.error}
                for s in self.sessions.values() if s.owner==owner]

    async def stop(self, sid: str, owner: str) -> dict:
        s=self._check(sid,owner)
        if s.task and not s.task.done(): s.task.cancel()
        s.complete=True
        return {"session_id":sid,"stopped":True}
