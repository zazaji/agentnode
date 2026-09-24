import hmac
from fastapi import Header, HTTPException
from .config import AppConfig, token_hash
from ..models import Principal, Role, ROLE_SCOPES

class AuthManager:
    def __init__(self,cfg:AppConfig): self.cfg=cfg
    def authenticate(self,token:str)->Principal:
        hv=token_hash(token)
        for name,rec in self.cfg.auth.tokens.items():
            if hmac.compare_digest(hv,rec.get("hash","")):
                role=Role(rec.get("role","viewer")); return Principal(name=name,role=role,scopes=ROLE_SCOPES[role])
        raise HTTPException(401,"invalid token")
    def dependency(self):
        async def dep(authorization:str|None=Header(default=None)):
            if not authorization or not authorization.lower().startswith("bearer "): raise HTTPException(401,"Bearer token required")
            return self.authenticate(authorization.split(None,1)[1])
        return dep
def require(p:Principal,scope:str):
    if not p.allowed(scope): raise HTTPException(403,f"scope required: {scope}")
