from __future__ import annotations
import platform
from multiprocessing.connection import Client
from typing import Any
from ..core.auth import require
from .com import OfficeCOM


class OfficeManager:
    """Route Office automation to the interactive Desktop Worker on Windows.

    A LocalSystem service lives in Session 0, while Office applications and user
    profiles live in the interactive session. The Desktop Worker is therefore the
    preferred execution context. Core fallback is intentionally opt-in.
    """
    def __init__(self,cfg):
        self.cfg=cfg; self.local=OfficeCOM(cfg)

    def _use_worker(self):
        return platform.system()=='Windows' and self.cfg.desktop.use_worker_on_windows and self.cfg.office.use_desktop_worker

    def _worker(self,method:str,payload:dict[str,Any]):
        c=Client(self.cfg.desktop.worker_pipe,family='AF_PIPE',authkey=self.cfg.desktop.worker_secret.encode())
        try:
            c.send({'op':'office','method':method,'payload':payload}); res=c.recv()
            if isinstance(res,dict) and res.get('error'): raise RuntimeError(res['error'])
            return res
        finally:
            c.close()

    def _call(self,method:str,payload:dict[str,Any],p,write=False):
        require(p,'office.write' if write else 'office.read')
        if not self.cfg.office.enabled: raise RuntimeError('Office COM is disabled in config')
        if self._use_worker():
            try: return self._worker(method,payload)
            except Exception as e:
                if not self.cfg.office.allow_core_fallback:
                    raise RuntimeError(f'Office Desktop Worker unavailable: {e}') from e
                out=self._local_call(method,payload,p)
                if isinstance(out,dict): out.setdefault('_worker_warning',str(e))
                return out
        return self._local_call(method,payload,p)

    def _local_call(self,method,payload,p):
        mapping={
            'excel_read': self.local.excel_read,
            'excel_write': self.local.excel_write,
            'excel_format': self.local.excel_format,
            'word_text': self.local.word_text,
            'word_replace': self.local.word_replace,
            'word_insert_table': self.local.word_insert_table,
            'powerpoint_read': self.local.powerpoint_read,
            'powerpoint_add_text_slide': self.local.powerpoint_add_text_slide,
        }
        fn=mapping.get(method)
        if not fn: raise ValueError('unsupported Office operation')
        return fn(p,**payload)

    def available(self):
        return self.local.available()

    def status(self,p):
        require(p,'office.read')
        return {
            'enabled':self.cfg.office.enabled,
            'local_com_available':self.local.available(),
            'execution_mode':'desktop-worker' if self._use_worker() else 'core',
            'core_fallback':self.cfg.office.allow_core_fallback,
        }

    def excel_read(self,p,workbook,sheet,cell_range): return self._call('excel_read',locals_payload(workbook=workbook,sheet=sheet,cell_range=cell_range),p)
    def excel_write(self,p,workbook,sheet,cell_range,value,save=True): return self._call('excel_write',locals_payload(workbook=workbook,sheet=sheet,cell_range=cell_range,value=value,save=save),p,True)
    def excel_format(self,p,workbook,sheet,cell_range,formatting): return self._call('excel_format',locals_payload(workbook=workbook,sheet=sheet,cell_range=cell_range,formatting=formatting),p,True)
    def word_text(self,p,document): return self._call('word_text',{'document':document},p)
    def word_replace(self,p,document,old,new): return self._call('word_replace',{'document':document,'old':old,'new':new},p,True)
    def word_insert_table(self,p,document,rows,at_end=True): return self._call('word_insert_table',{'document':document,'rows':rows,'at_end':at_end},p,True)
    def powerpoint_read(self,p,presentation): return self._call('powerpoint_read',{'presentation':presentation},p)
    def powerpoint_add_text_slide(self,p,presentation,title,body,save_as=None): return self._call('powerpoint_add_text_slide',{'presentation':presentation,'title':title,'body':body,'save_as':save_as},p,True)


def locals_payload(**kwargs):
    return kwargs
