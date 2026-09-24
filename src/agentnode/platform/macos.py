from .base import PlatformAdapter,CommandSpec
class MacAdapter(PlatformAdapter):
    name="macos"
    def shell(self,command,shell=None): return CommandSpec([(shell or "/bin/zsh"),"-lc",command])
    def service_command(self,action,name):
        if action=="status": return CommandSpec(["launchctl","print",name])
        return CommandSpec(["launchctl",action,name])
    def capabilities(self): return {**super().capabilities(),"accessibility":True,"screencapturekit":True}
