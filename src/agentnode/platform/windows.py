import subprocess
from .base import PlatformAdapter,CommandSpec
class WindowsAdapter(PlatformAdapter):
    name="windows"
    def shell(self,command,shell=None):
        sh=(shell or "powershell").lower()
        if sh in {"cmd","cmd.exe"}: return CommandSpec(["cmd.exe","/d","/s","/c",command],creationflags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0),start_new_session=False)
        return CommandSpec(["powershell.exe","-NoLogo","-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-Command",command],creationflags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0),start_new_session=False)
    def service_command(self,action,name):
        amap={"start":"Start-Service","stop":"Stop-Service","restart":"Restart-Service","status":"Get-Service"}; verb=amap[action]
        return self.shell(f"{verb} -Name '{name.replace(chr(39),chr(39)*2)}'","powershell")
    def capabilities(self): return {**super().capabilities(),"uia":True,"win32":True,"com":True,"session_worker":True}
