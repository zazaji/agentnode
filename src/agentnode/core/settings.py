from __future__ import annotations
import os, tempfile, threading
from pathlib import Path
from typing import Any
import yaml
from .config import AppConfig

EDITABLE={
    "shell.default", "shell.timeout_s", "shell.output_limit", "shell.allow_super_mode", "shell.blocked_fragments",
    "files.allowed_roots", "files.max_read_bytes", "files.max_write_bytes", "files.default_read_lines", "files.default_write_lines", "files.fuzzy_edit_min_similarity",
    "desktop.enabled", "desktop.ocr_provider", "browser.enabled", "browser.cdp_url", "browser.allow_remote", "browser.timeout_s", "browser.max_snapshot_chars", "browser.max_screenshot_bytes", "office.enabled", "office.use_desktop_worker", "office.allow_core_fallback", "mesh.max_hops", "mesh.forward_policy.mode", "mesh.forward_policy.offload_after", "mesh.forward_policy.max_forwards", "mesh.helper_key", "agent.default_runtime",
}
_LOCK=threading.RLock()

def _redact(obj:Any,key:str=""):
    if any(x in key.lower() for x in ("token","secret","api_key","password","authorization","hash","helper_key")): return "***"
    if isinstance(obj,dict): return {k:_redact(v,k) for k,v in obj.items()}
    if isinstance(obj,list): return [_redact(v,key) for v in obj]
    return obj

class SettingsManager:
    def __init__(self,path:str|Path,cfg:AppConfig): self.path=Path(path); self.cfg=cfg
    def view(self):
        return {"config":_redact(self.cfg.model_dump()),"editable":sorted(EDITABLE),"restart_required_for":["host","port","data_dir","http.*","auth.*","desktop.worker_*","mesh.peers","llm.providers"]}
    def _atomic_save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        text=yaml.safe_dump(self.cfg.model_dump(),sort_keys=False)
        with _LOCK:
            fd,tmp=tempfile.mkstemp(prefix=self.path.name+".",suffix=".tmp",dir=str(self.path.parent))
            try:
                with os.fdopen(fd,"w",encoding="utf-8") as f: f.write(text); f.flush(); os.fsync(f.fileno())
                if self.path.exists():
                    backup=self.path.with_suffix(self.path.suffix+".bak")
                    try: backup.write_bytes(self.path.read_bytes())
                    except OSError: pass
                os.replace(tmp,self.path)
                try: os.chmod(self.path,0o600)
                except OSError: pass
            finally:
                try:
                    if os.path.exists(tmp): os.unlink(tmp)
                except OSError: pass
    def set(self,key:str,value:Any):
        if key not in EDITABLE: raise ValueError(f"configuration key is not runtime-editable: {key}")
        parts=key.split("."); raw=self.cfg.model_dump(); d=raw
        for part in parts[:-1]: d=d[part]
        d[parts[-1]]=value
        new=AppConfig.model_validate(raw)
        self.cfg.__dict__.update(new.__dict__); self._atomic_save()
        d2=self.cfg
        for part in parts[:-1]: d2=getattr(d2,part)
        return {"key":key,"value":_redact(getattr(d2,parts[-1]),parts[-1]),"saved":True}
