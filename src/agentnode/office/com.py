from __future__ import annotations
import platform
from typing import Any
from ..core.auth import require


class OfficeCOM:
    """Optional Windows Office automation adapter.

    Calls are intentionally small and deterministic. Higher-level agents should
    prefer these native APIs for structured Office work and use GUI automation
    only when no equivalent API is available.
    """
    def __init__(self,cfg): self.cfg=cfg

    def available(self):
        if platform.system()!='Windows': return False
        try: import win32com.client; return True
        except Exception: return False

    def _dispatch(self,prog_id:str):
        if not self.cfg.office.enabled: raise RuntimeError('Office COM is disabled in config')
        if not self.available(): raise RuntimeError('Office COM requires Windows + pywin32 + Microsoft Office')
        import win32com.client
        try: return win32com.client.GetActiveObject(prog_id)
        except Exception: return win32com.client.Dispatch(prog_id)

    # Excel -----------------------------------------------------------------
    def excel_read(self,p,workbook:str,sheet:str,cell_range:str):
        require(p,'office.read'); app=self._dispatch('Excel.Application'); wb=app.Workbooks.Open(workbook,ReadOnly=True)
        try:
            v=wb.Worksheets(sheet).Range(cell_range).Value
            return {'workbook':workbook,'sheet':sheet,'range':cell_range,'value':v}
        finally: wb.Close(False)

    def excel_write(self,p,workbook:str,sheet:str,cell_range:str,value:Any,save:bool=True):
        require(p,'office.write'); app=self._dispatch('Excel.Application'); wb=app.Workbooks.Open(workbook)
        try:
            wb.Worksheets(sheet).Range(cell_range).Value=value
            if save: wb.Save()
            return {'ok':True,'workbook':workbook,'sheet':sheet,'range':cell_range}
        finally: wb.Close(save)

    def excel_format(self,p,workbook:str,sheet:str,cell_range:str,formatting:dict[str,Any]):
        require(p,'office.write'); app=self._dispatch('Excel.Application'); wb=app.Workbooks.Open(workbook)
        try:
            r=wb.Worksheets(sheet).Range(cell_range)
            if 'bold' in formatting: r.Font.Bold=bool(formatting['bold'])
            if 'italic' in formatting: r.Font.Italic=bool(formatting['italic'])
            if 'font_size' in formatting: r.Font.Size=float(formatting['font_size'])
            if 'number_format' in formatting: r.NumberFormat=str(formatting['number_format'])
            if 'horizontal_alignment' in formatting: r.HorizontalAlignment=int(formatting['horizontal_alignment'])
            if 'wrap_text' in formatting: r.WrapText=bool(formatting['wrap_text'])
            wb.Save(); return {'ok':True,'workbook':workbook,'sheet':sheet,'range':cell_range,'formatting':formatting}
        finally: wb.Close(True)

    # Word ------------------------------------------------------------------
    def word_text(self,p,document:str):
        require(p,'office.read'); app=self._dispatch('Word.Application'); doc=app.Documents.Open(document,ReadOnly=True)
        try:return {'document':document,'text':doc.Content.Text}
        finally:doc.Close(False)

    def word_replace(self,p,document:str,old:str,new:str):
        require(p,'office.write'); app=self._dispatch('Word.Application'); doc=app.Documents.Open(document)
        try:
            find=doc.Content.Find; find.ClearFormatting(); find.Text=old; find.Replacement.ClearFormatting(); find.Replacement.Text=new
            ok=find.Execute(Replace=2); doc.Save(); return {'ok':bool(ok),'document':document}
        finally:doc.Close(False)

    def word_insert_table(self,p,document:str,rows:list[list[Any]],at_end:bool=True):
        require(p,'office.write'); app=self._dispatch('Word.Application'); doc=app.Documents.Open(document)
        try:
            if not rows: return {'ok':True,'rows':0,'cols':0}
            cols=max(len(x) for x in rows); rng=doc.Content
            if at_end: rng.Collapse(0)  # wdCollapseEnd
            table=doc.Tables.Add(rng,len(rows),cols)
            for i,row in enumerate(rows,1):
                for j,val in enumerate(row,1): table.Cell(i,j).Range.Text='' if val is None else str(val)
            doc.Save(); return {'ok':True,'document':document,'rows':len(rows),'cols':cols}
        finally: doc.Close(False)

    # PowerPoint ------------------------------------------------------------
    def powerpoint_read(self,p,presentation:str):
        require(p,'office.read'); app=self._dispatch('PowerPoint.Application'); pres=app.Presentations.Open(presentation,WithWindow=False)
        try:
            slides=[]
            for slide in pres.Slides:
                texts=[]
                for shape in slide.Shapes:
                    try:
                        if shape.HasTextFrame and shape.TextFrame.HasText:
                            texts.append(shape.TextFrame.TextRange.Text)
                    except Exception: pass
                slides.append({'index':slide.SlideIndex,'texts':texts})
            return {'presentation':presentation,'slide_count':pres.Slides.Count,'slides':slides}
        finally: pres.Close()

    def powerpoint_add_text_slide(self,p,presentation:str,title:str,body:str,save_as:str|None=None):
        require(p,'office.write'); app=self._dispatch('PowerPoint.Application')
        try:
            pres=app.Presentations.Open(presentation,WithWindow=False) if presentation else app.Presentations.Add()
            # ppLayoutText = 2 (title + body). Use numeric constant to avoid generated wrappers.
            slide=pres.Slides.Add(pres.Slides.Count+1,2)
            try: slide.Shapes.Title.TextFrame.TextRange.Text=title
            except Exception: pass
            try: slide.Shapes.Placeholders(2).TextFrame.TextRange.Text=body
            except Exception: pass
            if save_as: pres.SaveAs(save_as)
            else: pres.Save()
            return {'ok':True,'slide_index':slide.SlideIndex,'presentation':save_as or presentation}
        finally:
            try: pres.Close()
            except Exception: pass
