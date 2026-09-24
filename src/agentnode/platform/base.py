from __future__ import annotations
import abc,platform
from dataclasses import dataclass
@dataclass
class CommandSpec:
    argv:list[str]; creationflags:int=0; start_new_session:bool=True
class PlatformAdapter(abc.ABC):
    name=platform.system().lower()
    @abc.abstractmethod
    def shell(self,command:str,shell:str|None=None)->CommandSpec: ...
    @abc.abstractmethod
    def service_command(self,action:str,name:str)->CommandSpec: ...
    def capabilities(self): return {"platform":self.name,"shell":True,"services":True}
