from .capture import CaptureBackend
from .ocr import OCRManager
from .windows_uia import WindowsUIA
from .input import InputController
from .windows_native import WindowsNative

class LocalDesktopBackend:
    def __init__(self,cfg):
        self.capture_backend=CaptureBackend(); self.ocr=OCRManager(cfg.desktop.ocr_provider); self.uia=WindowsUIA(); self.input=InputController(); self.native=WindowsNative()
    def observe(self,include_image=True,ocr=False):
        cap=self.capture_backend.capture(); result={'capture':cap,'windows':self.uia.windows()}
        if ocr and cap.get('png_base64'): result['ocr']=self.ocr.recognize_base64(cap['png_base64'])
        if not include_image and 'png_base64' in cap:
            cap=dict(cap); cap.pop('png_base64',None); result['capture']=cap
        return result
    def tree(self,title_re='.*'): return self.uia.tree(title_re)
    def act(self,a): return self.input.act(a)

    def native_windows(self): return self.native.windows()
    def window_control(self,hwnd,action,**kw): return self.native.control(hwnd,action,**kw)
    def uia_find(self,title_re=".*",name=None,control_type=None): return self.uia.find(title_re,name,control_type)
    def uia_invoke(self,title_re=".*",name=None,automation_id=None): return self.uia.invoke(title_re,name,automation_id)
