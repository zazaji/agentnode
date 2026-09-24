from __future__ import annotations
class LLMRegistry:
    def __init__(self,cfg): self.cfg=cfg
    def list(self): return {"providers":{k:{**v,"api_key":"***" if v.get('api_key') else None} for k,v in self.cfg.llm.providers.items()},"profiles":self.cfg.llm.profiles,"routing":self.cfg.llm.routing}
    def resolve(self,profile=None,capability=None):
        name=profile or (self.cfg.llm.routing.get(capability) if capability else None)
        if not name:return None
        p=self.cfg.llm.profiles.get(name)
        if not p:return None
        prov=self.cfg.llm.providers.get(p.get('provider'),{})
        return {"profile":name,"provider":p.get('provider'),"model":p.get('model'),"base_url":prov.get('base_url'),"api_key_env":prov.get('api_key_env')}
