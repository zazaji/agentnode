from .base import PlatformAdapter,CommandSpec
class LinuxAdapter(PlatformAdapter):
    name="linux"
    def shell(self,command,shell=None): return CommandSpec([(shell or "/bin/bash"),"-lc",command])
    def service_command(self,action,name):
        verb={"status":"status","start":"start","stop":"stop","restart":"restart"}[action]; return CommandSpec(["systemctl",verb,name])
    def capabilities(self): return {**super().capabilities(),"at_spi":True,"wayland_limited":True}
