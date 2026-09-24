from __future__ import annotations
import base64,io
class OCRManager:
    def __init__(self,provider="auto"): self.provider=provider; self._rapid=None
    def recognize_base64(self,data:str):
        try:
            from PIL import Image
            import numpy as np
            from rapidocr_onnxruntime import RapidOCR
            if self._rapid is None:self._rapid=RapidOCR()
            img=np.array(Image.open(io.BytesIO(base64.b64decode(data))))
            result,_=self._rapid(img); out=[]
            for item in result or []: out.append({"box":item[0],"text":item[1],"confidence":float(item[2])})
            return {"provider":"rapidocr","items":out}
        except Exception as e: return {"provider":self.provider,"available":False,"error":str(e),"items":[]}
