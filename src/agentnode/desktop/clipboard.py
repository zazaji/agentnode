from __future__ import annotations
import platform, subprocess
from ..core.auth import require
class ClipboardManager:
    def get(self,p):
        require(p,'clipboard.read')
        sys=platform.system()
        try:
            if sys=='Windows':
                cp=subprocess.run(['powershell.exe','-NoProfile','-Command','Get-Clipboard -Raw'],capture_output=True,text=True,timeout=5)
            elif sys=='Darwin': cp=subprocess.run(['pbpaste'],capture_output=True,text=True,timeout=5)
            else: cp=subprocess.run(['sh','-lc','command -v wl-paste >/dev/null && wl-paste || xclip -selection clipboard -o'],capture_output=True,text=True,timeout=5)
            return {'text':cp.stdout,'ok':cp.returncode==0}
        except Exception as e:return {'ok':False,'error':str(e)}
    def set(self,p,text):
        require(p,'clipboard.write'); sys=platform.system()
        try:
            if sys=='Windows':
                cp=subprocess.run(['powershell.exe','-NoProfile','-Command','Set-Clipboard -Value $input'],input=text,capture_output=True,text=True,timeout=5)
            elif sys=='Darwin': cp=subprocess.run(['pbcopy'],input=text,capture_output=True,text=True,timeout=5)
            else: cp=subprocess.run(['sh','-lc','command -v wl-copy >/dev/null && wl-copy || xclip -selection clipboard'],input=text,capture_output=True,text=True,timeout=5)
            return {'ok':cp.returncode==0}
        except Exception as e:return {'ok':False,'error':str(e)}
