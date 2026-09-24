from __future__ import annotations
import argparse
from multiprocessing.connection import Listener
from .local import LocalDesktopBackend
from ..core.config import load_config
from ..models import DesktopAct, Principal, Role, ROLE_SCOPES
from ..office.com import OfficeCOM

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config',required=True); args=ap.parse_args(); cfg=load_config(args.config)
    backend=LocalDesktopBackend(cfg)
    office=OfficeCOM(cfg)
    office_principal=Principal(name="desktop-worker",role=Role.super,scopes=ROLE_SCOPES[Role.super])
    listener=Listener(cfg.desktop.worker_pipe,family='AF_PIPE',authkey=cfg.desktop.worker_secret.encode())
    while True:
        conn=listener.accept()
        try:
            req=conn.recv(); op=req.get('op')
            if op=='observe': res=backend.observe(req.get('include_image',True),req.get('ocr',False))
            elif op=='tree': res=backend.tree(req.get('title_re','.*'))
            elif op=='act': res=backend.act(DesktopAct.model_validate(req['action']))
            elif op=='native_windows': res=backend.native_windows()
            elif op=='window_control': res=backend.window_control(req['hwnd'],req['action'],x=req.get('x'),y=req.get('y'),w=req.get('w'),h=req.get('h'))
            elif op=='uia_find': res=backend.uia_find(req.get('title_re','.*'),req.get('name'),req.get('control_type'))
            elif op=='uia_invoke': res=backend.uia_invoke(req.get('title_re','.*'),req.get('name'),req.get('automation_id'))
            elif op=='office':
                method=req.get('method'); payload=req.get('payload') or {}
                allowed={
                    'excel_read': office.excel_read,
                    'excel_write': office.excel_write,
                    'excel_format': office.excel_format,
                    'word_text': office.word_text,
                    'word_replace': office.word_replace,
                    'word_insert_table': office.word_insert_table,
                    'powerpoint_read': office.powerpoint_read,
                    'powerpoint_add_text_slide': office.powerpoint_add_text_slide,
                }
                fn=allowed.get(method)
                if fn is None: raise ValueError('unsupported Office operation')
                res=fn(office_principal,**payload)
            else: res={'error':'unknown op'}
            conn.send(res)
        except Exception as e:
            try: conn.send({'error':f'{type(e).__name__}: {e}'})
            except Exception: pass
        finally: conn.close()
if __name__=='__main__': main()
