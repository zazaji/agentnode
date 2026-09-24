from __future__ import annotations
import platform,socket,time,psutil
from .auth import require
from ..models import Principal
from ..platform import get_platform_adapter
class SystemManager:
    def __init__(self): self.platform=get_platform_adapter()
    def info(self,p:Principal):
        require(p,"node.read")
        vm=psutil.virtual_memory(); return {"node":socket.gethostname(),"platform":platform.platform(),"python":platform.python_version(),"cpu_percent":psutil.cpu_percent(),"memory":{"percent":vm.percent,"used":vm.used,"total":vm.total},"boot_time":psutil.boot_time(),"capabilities":self.platform.capabilities()}
    def processes(self,p:Principal,limit=200):
        require(p,"process.read"); out=[]
        for x in psutil.process_iter(['pid','name','username','cpu_percent','memory_percent']):
            try: out.append(x.info)
            except Exception: pass
        return sorted(out,key=lambda x:x.get('memory_percent') or 0,reverse=True)[:limit]
    def kill(self,pid:int,p:Principal):
        require(p,"process.write"); proc=psutil.Process(pid); proc.terminate(); return {"pid":pid,"status":"terminate_sent"}
