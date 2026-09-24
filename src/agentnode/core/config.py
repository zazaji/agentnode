from __future__ import annotations
import os, secrets, hashlib
from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field

class AuthConfig(BaseModel):
    tokens:dict[str,dict[str,str]]=Field(default_factory=dict)
class ShellConfig(BaseModel):
    default:str="auto"; timeout_s:int=120; output_limit:int=2_000_000; allow_super_mode:bool=False; blocked_fragments:list[str]=Field(default_factory=lambda:["agentnode token","config.yaml"])
class FilesConfig(BaseModel):
    allowed_roots:list[str]=Field(default_factory=lambda:[str(Path.home())])
    max_read_bytes:int=4_000_000
    max_write_bytes:int=8_000_000
    default_read_lines:int=1000
    default_write_lines:int=200
    fuzzy_edit_min_similarity:float=0.86
class DesktopConfig(BaseModel):
    enabled:bool=True; ocr_provider:str="auto"; screenshot_dir:str="data/screenshots"; use_worker_on_windows:bool=True; worker_pipe:str=r"\\.\pipe\AgentNodeDesktop"; worker_secret:str=""
class ForwardPolicy(BaseModel):
    mode:str="off"                      # off | offload | distribute
    offload_after:int=3                 # offload: hand task off when >N in-flight requests
    max_forwards:int=3                  # relay budget: max forward hops for a task
class MeshConfig(BaseModel):
    node_id:str=""; max_hops:int=4
    helper_key:str=""                   # shared key that marks this node as an auxiliary (helper) node
    forward_policy:ForwardPolicy=Field(default_factory=ForwardPolicy)
    peers:dict[str,dict[str,str]]=Field(default_factory=dict)
class LLMConfig(BaseModel):
    providers:dict[str,dict[str,Any]]=Field(default_factory=dict); profiles:dict[str,dict[str,Any]]=Field(default_factory=dict); routing:dict[str,str]=Field(default_factory=dict)
class AgentConfig(BaseModel):
    default_runtime:str="pi"; runtimes:dict[str,dict[str,Any]]=Field(default_factory=lambda:{"pi":{"enabled":False,"executable":"pi"}})
class BrowserConfig(BaseModel):
    enabled:bool=False; cdp_url:str="http://127.0.0.1:9222"; allow_remote:bool=False; timeout_s:int=15; max_snapshot_chars:int=2_000_000; max_screenshot_bytes:int=8_000_000
class OfficeConfig(BaseModel):
    enabled:bool=False; use_desktop_worker:bool=True; allow_core_fallback:bool=False
class HttpConfig(BaseModel):
    max_request_bytes:int=8_000_000; trusted_hosts:list[str]=Field(default_factory=lambda:["127.0.0.1","localhost","testserver"])
class AppConfig(BaseModel):
    host:str="127.0.0.1"; port:int=8765; data_dir:str="data"; http:HttpConfig=Field(default_factory=HttpConfig); auth:AuthConfig=Field(default_factory=AuthConfig); shell:ShellConfig=Field(default_factory=ShellConfig); files:FilesConfig=Field(default_factory=FilesConfig); desktop:DesktopConfig=Field(default_factory=DesktopConfig); mesh:MeshConfig=Field(default_factory=MeshConfig); llm:LLMConfig=Field(default_factory=LLMConfig); agent:AgentConfig=Field(default_factory=AgentConfig); browser:BrowserConfig=Field(default_factory=BrowserConfig); office:OfficeConfig=Field(default_factory=OfficeConfig)

def token_hash(v:str)->str: return hashlib.sha256(v.encode()).hexdigest()
def load_config(path:str|Path)->AppConfig:
    p=Path(path); data=yaml.safe_load(p.read_text('utf-8')) if p.exists() else {}
    cfg=AppConfig.model_validate(data or {})
    if not cfg.mesh.node_id:
        import socket; cfg.mesh.node_id=socket.gethostname().lower()
    return cfg
def init_config(path:str|Path)->tuple[AppConfig,dict[str,str]]:
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    raw={k:secrets.token_urlsafe(32) for k in ("operator","super","node")}
    cfg=AppConfig()
    cfg.desktop.worker_secret=secrets.token_urlsafe(32)
    cfg.auth.tokens={k:{"hash":token_hash(v),"role":k if k!="operator" else "operator"} for k,v in raw.items()}
    p.write_text(yaml.safe_dump(cfg.model_dump(),sort_keys=False),encoding='utf-8')
    try: os.chmod(p,0o600)
    except OSError: pass
    return cfg,raw
