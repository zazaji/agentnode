from __future__ import annotations
import base64,io,time
from pathlib import Path
class CaptureBackend:
    def capture(self,monitor=1):
        try:
            import mss
            from PIL import Image
            with mss.mss() as s:
                m=s.monitors[monitor if monitor < len(s.monitors) else 1]; raw=s.grab(m); img=Image.frombytes('RGB',raw.size,raw.rgb); bio=io.BytesIO(); img.save(bio,format='PNG'); b=bio.getvalue()
                return {"width":img.width,"height":img.height,"png_base64":base64.b64encode(b).decode(),"timestamp":time.time(),"backend":"mss"}
        except Exception as e: return {"available":False,"error":str(e),"timestamp":time.time()}
