from __future__ import annotations
import re
from fastapi import HTTPException
from .config import AppConfig
from ..models import Principal
READ_HINTS=("get-","show ","list ","status","query","ipconfig","whoami","hostname","uname","ps ","tasklist","systeminfo","df ","free ","uptime","ping ")
DANGEROUS=("format ","diskpart","remove-item -recurse","del /s","rm -rf /","shutdown","reboot","stop-computer","restart-computer","bcdedit","cipher /w")
def classify(command:str)->str:
    c=command.strip().lower()
    if any(x in c for x in DANGEROUS): return "R4"
    if any(x in c for x in ("set-service","restart-service","stop-service","start-service","reg add","sc.exe config","systemctl restart","systemctl stop","launchctl unload","sudo ")): return "R3"
    if c.startswith(READ_HINTS): return "R0"
    return "R2"
def check_shell(cfg:AppConfig,p:Principal,command:str,super_mode:bool,delegated:bool=False):
    if super_mode:
        if not cfg.shell.allow_super_mode or not p.allowed("*"): raise HTTPException(403,"super mode disabled or super role required")
        return
    low=command.lower()
    if any(x.lower() in low for x in cfg.shell.blocked_fragments): raise HTTPException(403,"command blocked by policy")
    if classify(command)=="R4": raise HTTPException(403,"destructive command requires explicit super_mode")
    # A request forwarded through the mesh (trace_id/hops present) is authorized
    # by the caller's mesh.delegate scope, not by shell.read/shell.write. The
    # mesh-delegate account (node role) cannot otherwise hold shell.write, so
    # delegated work passes through this path instead.
    if delegated:
        if not p.allowed("mesh.delegate"): raise HTTPException(403,"delegated shell requires mesh.delegate")
        return
    scope="shell.read" if classify(command)=="R0" else "shell.write"
    if not p.allowed(scope): raise HTTPException(403,f"scope required: {scope}")
