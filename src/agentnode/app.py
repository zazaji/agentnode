from __future__ import annotations
import asyncio, contextlib, os, time
from pathlib import Path
from typing import Any
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse
from .core.config import load_config
from .core.auth import AuthManager, require
from .core.audit import AuditLog
from .core.jobs import JobStore
from .core.events import EventStore
from .core.shell import ShellRunner
from .core.files import FileManager
from .core.search import SearchManager
from .core.history import ToolHistory
from .core.codeexec import CodeExecutor
from .core.settings import SettingsManager
from .core.system import SystemManager
from .core.terminal import TerminalManager
from .core.services import ServiceManager
from .desktop.manager import DesktopManager
from .desktop.clipboard import ClipboardManager
from .agent.runtime import AgentRuntimeManager
from .agent.llm import LLMRegistry
from .mesh.router import MeshRouter
from .plugins.documents import DocumentManager
from .browser import CDPManager
from .office import OfficeManager
from .desktop.graph import DesktopGraph
from .models import Principal, ShellRequest, AgentRequest, DelegateRequest, CoordinateRequest, ForwardRequest, DesktopAct
from .web.console import HTML
from .core.request_context import current_principal
from .core.http_security import BodyLimitMiddleware, SecurityHeadersMiddleware

class FileWrite(BaseModel): path:str; data:str; atomic:bool=True; mode:str="rewrite"
class FileRead(BaseModel): path:str; offset:int=0; limit:int|None=None
class SmartFileRead(BaseModel): path:str; offset:int=0; length:int=1000; sheet:str|None=None; cell_range:str|None=None; include_binary:bool=False
class MultiFileRead(BaseModel): paths:list[str]; smart:bool=True; limit_per_file:int=1000
class FileReplace(BaseModel): path:str; old:str; new:str; expected:int=1; fuzzy:bool=False; min_similarity:float=0.86; dry_run:bool=False
class FileSearch(BaseModel): root:str; pattern:str; limit:int=200
class FilePath(BaseModel): path:str
class FileMove(BaseModel): source:str; destination:str; overwrite:bool=False
class SearchStart(BaseModel):
    root:str; pattern:str; search_type:str="content"; file_pattern:str|None=None; ignore_case:bool=True
    include_hidden:bool=False; max_results:int=2000; literal:bool=False
class TerminalStart(BaseModel): command:str; shell:str|None=None; cwd:str|None=None; interactive:bool=False
class TerminalWrite(BaseModel): data:str
class ClipboardSet(BaseModel): text:str
class ServiceAction(BaseModel): action:str; name:str
class WindowControl(BaseModel): hwnd:int; action:str; x:int|None=None; y:int|None=None; w:int|None=None; h:int|None=None
class UIAFind(BaseModel): title_re:str='.*'; name:str|None=None; control_type:str|None=None
class UIAInvoke(BaseModel): title_re:str='.*'; name:str|None=None; automation_id:str|None=None
class ConfigSet(BaseModel): key:str; value:Any
class CodeRun(BaseModel): language:str; code:str; timeout_s:int=60; cwd:str|None=None
class XlsxRead(BaseModel): path:str; sheet:str|None=None; cell_range:str|None=None; formulas:bool=True
class XlsxWrite(BaseModel): path:str; sheet:str; start_cell:str; values:list[list[Any]]; create:bool=False
class XlsxAppend(BaseModel): path:str; sheet:str; values:list[list[Any]]
class DocxCreate(BaseModel): path:str; paragraphs:list[str]; title:str|None=None
class DocxReplace(BaseModel): path:str; old:str; new:str; expected:int|None=None
class PdfRead(BaseModel): path:str; start_page:int=0; pages:int=20
class PdfMerge(BaseModel): inputs:list[str]; output:str
class BrowserEval(BaseModel): target_id:str; expression:str
class BrowserNavigate(BaseModel): target_id:str; url:str
class BrowserSelector(BaseModel): target_id:str; selector:str
class BrowserType(BaseModel): target_id:str; selector:str; text:str; clear:bool=True
class BrowserNewTab(BaseModel): url:str="about:blank"
class OfficeExcelRead(BaseModel): workbook:str; sheet:str; cell_range:str
class OfficeExcelWrite(BaseModel): workbook:str; sheet:str; cell_range:str; value:Any; save:bool=True
class OfficeExcelFormat(BaseModel): workbook:str; sheet:str; cell_range:str; formatting:dict[str,Any]
class OfficeWordRead(BaseModel): document:str
class OfficeWordReplace(BaseModel): document:str; old:str; new:str
class OfficeWordTable(BaseModel): document:str; rows:list[list[Any]]; at_end:bool=True
class OfficePptRead(BaseModel): presentation:str
class OfficePptAddSlide(BaseModel): presentation:str; title:str; body:str; save_as:str|None=None

def create_app(config_path:str|None=None):
    cfg_path=config_path or os.getenv('AGENTNODE_CONFIG','config.yaml')
    cfg=load_config(cfg_path)
    data=Path(cfg.data_dir); data.mkdir(parents=True,exist_ok=True)
    auth=AuthManager(cfg); principal_dep=auth.dependency()
    audit=AuditLog(data/'audit.jsonl'); events=EventStore(data/'events'); jobs=JobStore(data/'jobs.jsonl')
    history=ToolHistory(data/'tool-history.jsonl'); settings=SettingsManager(cfg_path,cfg); codeexec=CodeExecutor()
    shell=ShellRunner(cfg); files=FileManager(cfg); searches=SearchManager(files); system=SystemManager(); terms=TerminalManager(); services=ServiceManager()
    desktop=DesktopManager(cfg); clipboard=ClipboardManager(); runtimes=AgentRuntimeManager(cfg,events); llm=LLMRegistry(cfg); mesh=MeshRouter(cfg); documents=DocumentManager(files); browser=CDPManager(cfg); office=OfficeManager(cfg); desktop_graph=DesktopGraph(desktop)
    async def mesh_local_executor(action:str,payload:dict,trace_id:str|None,hops:list[str],forwardable:bool):
        # Runs a relayed task on this node when a forward chain decides to execute
        # locally. The relaying peer's principal is active via current_principal.
        p=current_principal.get()
        if p is None: raise RuntimeError('no principal available for local mesh execution')
        if action=='shell':
            req=ShellRequest.model_validate(dict(payload)); req.trace_id=trace_id; req.hops=[*hops]
            return await shell.execute(req,p)
        if action=='agent':
            ar=AgentRequest.model_validate(dict(payload)); ar.trace_id=trace_id; ar.hops=[*hops]
            j=jobs.create('agent',p.name,{'prompt':ar.prompt,'cwd':ar.cwd,'runtime':ar.runtime})
            async def fn(job): return await runtimes.run(job,ar.prompt,ar.cwd,ar.runtime,ar.timeout_s)
            jobs.submit(j,fn)
            try: await jobs.tasks[j.id]
            except Exception: pass
            return jobs.get(j.id).model_dump()
        raise RuntimeError(f'unsupported forward action: {action}')
    mesh.local_executor=mesh_local_executor
    mcp=None
    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.server.transport_security import TransportSecuritySettings
        # FastMCP auto-enables rebinding protection for loopback hosts with a
        # loopback-only whitelist; mirror the deployment's trusted hosts instead.
        hosts=set(cfg.http.trusted_hosts)|{'127.0.0.1','localhost','[::1]'}
        allowed=[v for h in hosts for v in (h,h+':*')]
        mcp=FastMCP('AgentNode 3.2',stateless_http=True,streamable_http_path='/',
                    transport_security=TransportSecuritySettings(
                        enable_dns_rebinding_protection=True,
                        allowed_hosts=allowed,
                        allowed_origins=[]))
    except Exception:
        mcp=None

    @contextlib.asynccontextmanager
    async def lifespan(app):
        if mcp is not None:
            async with mcp.session_manager.run(): yield
        else: yield

    app=FastAPI(title='AgentNode',version='3.3.0',lifespan=lifespan)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(BodyLimitMiddleware,max_bytes=cfg.http.max_request_bytes)
    if cfg.http.trusted_hosts:
        app.add_middleware(TrustedHostMiddleware,allowed_hosts=cfg.http.trusted_hosts)
    app.state.ctx=locals()

    def json_error(status:int,exc:Exception):
        return JSONResponse(status_code=status,content={"detail":str(exc)})
    app.add_exception_handler(PermissionError,lambda req,exc: json_error(403,exc))
    app.add_exception_handler(FileNotFoundError,lambda req,exc: json_error(404,exc))
    app.add_exception_handler(FileExistsError,lambda req,exc: json_error(409,exc))
    app.add_exception_handler(KeyError,lambda req,exc: json_error(400,exc))
    app.add_exception_handler(ValueError,lambda req,exc: json_error(400,exc))
    app.add_exception_handler(RuntimeError,lambda req,exc: json_error(400,exc))
    app.add_exception_handler(TimeoutError,lambda req,exc: json_error(504,exc))

    def rec(tool,p,args,result=None,error=None,started=None,source="rest"):
        history.record(tool,p.name,args,result,error,int((time.time()-started)*1000) if started else None,source)

    @app.get('/',response_class=HTMLResponse)
    async def console(): return HTML
    @app.get('/health')
    async def health(): return {'ok':True,'version':'3.3.0','node_id':cfg.mesh.node_id,'documents':documents.capabilities(),'office_com':office.available(),'browser_cdp':cfg.browser.enabled,'mesh':{'helper':bool(cfg.mesh.helper_key),'forward_policy':cfg.mesh.forward_policy.model_dump()}}
    @app.get('/api/v1/node')
    async def node(p:Principal=Depends(principal_dep)): return system.info(p)

    @app.get('/api/v1/jobs')
    async def list_jobs(p:Principal=Depends(principal_dep)):
        require(p,'job.read'); return [j.model_dump() for j in jobs.list() if p.allowed('*') or j.owner==p.name]
    @app.get('/api/v1/jobs/{jid}')
    async def get_job(jid:str,p:Principal=Depends(principal_dep)):
        require(p,'job.read'); j=jobs.get(jid)
        if not j or (j.owner!=p.name and not p.allowed('*')): raise HTTPException(404,'job not found')
        return j.model_dump()
    @app.get('/api/v1/jobs/{jid}/events')
    async def job_events(jid:str,cursor:int=0,p:Principal=Depends(principal_dep)):
        j=jobs.get(jid)
        if not j or (j.owner!=p.name and not p.allowed('*')): raise HTTPException(404,'job not found')
        return events.read(jid,cursor)
    @app.post('/api/v1/jobs/{jid}/cancel')
    async def cancel_job(jid:str,p:Principal=Depends(principal_dep)):
        j=jobs.get(jid)
        if not j or (j.owner!=p.name and not p.allowed('*')): raise HTTPException(404,'job not found')
        return {'cancelled':jobs.cancel(jid)}

    @app.post('/api/v1/shell')
    async def shell_exec(req:ShellRequest,p:Principal=Depends(principal_dep)):
        st=time.time(); audit.emit('shell.request',p.name,{'super':req.super_mode,'background':req.background})
        if req.background:
            j=jobs.create('shell',p.name,req.model_dump())
            async def fn(job):
                events.emit(job.id,'phase',{'phase':'execute'}); r=await shell.execute(req,p,job); rec('shell.execute',p,req.model_dump(),r,started=st); return r
            jobs.submit(j,fn); return j.model_dump()
        try:
            r=await shell.execute(req,p); rec('shell.execute',p,req.model_dump(),r,started=st); return r
        except Exception as e:
            rec('shell.execute',p,req.model_dump(),error=str(e),started=st); raise

    @app.post('/api/v1/agent')
    async def agent(req:AgentRequest,p:Principal=Depends(principal_dep)):
        require(p,'agent.run'); j=jobs.create('agent',p.name,{'prompt':req.prompt,'cwd':req.cwd,'runtime':req.runtime}); st=time.time()
        async def fn(job):
            try:
                r=await runtimes.run(job,req.prompt,req.cwd,req.runtime,req.timeout_s); rec('agent.run',p,{'cwd':req.cwd,'runtime':req.runtime,'prompt':req.prompt},r,started=st); return r
            except Exception as e:
                rec('agent.run',p,{'cwd':req.cwd,'runtime':req.runtime,'prompt':req.prompt},error=str(e),started=st); raise
        jobs.submit(j,fn)
        if req.background:return j.model_dump()
        await jobs.tasks[j.id]; return jobs.get(j.id).model_dump()

    @app.get('/api/v1/runtime')
    async def runtime(p:Principal=Depends(principal_dep)):
        require(p,'node.read'); return {'agents':runtimes.available(),'llm':llm.list()}
    @app.post('/api/v1/code')
    async def code_run(req:CodeRun,p:Principal=Depends(principal_dep)):
        st=time.time()
        try:
            r=await codeexec.run(p,req.language,req.code,req.timeout_s,req.cwd); rec('code.execute',p,{'language':req.language,'cwd':req.cwd,'code':req.code},r,started=st); return r
        except Exception as e:
            rec('code.execute',p,{'language':req.language,'cwd':req.cwd,'code':req.code},error=str(e),started=st); raise
    @app.get('/api/v1/peers')
    async def peers(p:Principal=Depends(principal_dep)):
        require(p,'node.read'); return mesh.peers()
    @app.post('/api/v1/mesh/delegate')
    async def delegate(req:DelegateRequest,p:Principal=Depends(principal_dep)): return await mesh.delegate(p,req)
    @app.post('/api/v1/mesh/coordinate')
    async def coordinate(req:CoordinateRequest,p:Principal=Depends(principal_dep)):
        st=time.time()
        try:
            r=await mesh.coordinate(p,req); rec('mesh.coordinate',p,{'action':req.task.action,'peers':req.peers,'parallel':req.parallel},r,started=st); return r
        except Exception as e:
            rec('mesh.coordinate',p,{'action':req.task.action,'peers':req.peers,'parallel':req.parallel},error=str(e),started=st); raise
    @app.post('/api/v1/mesh/forward')
    async def forward(req:ForwardRequest,p:Principal=Depends(principal_dep),request:Request=None):
        helper_key=request.headers.get('x-agentnode-helper-key') if request is not None else None
        st=time.time(); tok=current_principal.set(p)
        try:
            r=await mesh.forward(p,req,helper_key); rec('mesh.forward',p,{'action':req.task.action,'target':req.target,'forwardable':req.forwardable,'mode':req.policy.mode if req.policy else None},r,started=st); return r
        except Exception as e:
            rec('mesh.forward',p,{'action':req.task.action,'target':req.target,'forwardable':req.forwardable},error=str(e),started=st); raise
        finally:
            current_principal.reset(tok)

    # Desktop-Commander-style filesystem intelligence
    @app.post('/api/v1/files/read')
    async def f_read(req:FileRead,p:Principal=Depends(principal_dep)): return files.read(req.path,p,req.offset,req.limit)
    @app.post('/api/v1/files/read-smart')
    async def f_read_smart(req:SmartFileRead,p:Principal=Depends(principal_dep)):
        st=time.time(); r=files.read_smart(req.path,p,req.offset,req.length,req.sheet,req.cell_range,req.include_binary); rec('file.read_smart',p,req.model_dump(),{'kind':r.get('kind'),'returned':r.get('returned')},started=st); return r
    @app.post('/api/v1/files/read-multiple')
    async def f_read_many(req:MultiFileRead,p:Principal=Depends(principal_dep)): return files.read_many(req.paths,p,req.smart,req.limit_per_file)
    @app.post('/api/v1/files/write')
    async def f_write(req:FileWrite,p:Principal=Depends(principal_dep)): return files.write(req.path,req.data,p,req.atomic,req.mode)
    @app.post('/api/v1/files/replace')
    async def f_replace(req:FileReplace,p:Principal=Depends(principal_dep)): return files.replace(req.path,req.old,req.new,p,req.expected,req.fuzzy,req.min_similarity,req.dry_run)
    @app.post('/api/v1/files/search')
    async def f_search(req:FileSearch,p:Principal=Depends(principal_dep)): return files.search(req.root,req.pattern,p,req.limit)
    @app.get('/api/v1/files/list')
    async def f_list(path:str,depth:int=1,p:Principal=Depends(principal_dep)): return files.list(path,p,depth)
    @app.get('/api/v1/files/info')
    async def f_info(path:str,p:Principal=Depends(principal_dep)): return files.info(path,p)
    @app.post('/api/v1/files/mkdir')
    async def f_mkdir(req:FilePath,p:Principal=Depends(principal_dep)): return files.mkdir(req.path,p)
    @app.post('/api/v1/files/move')
    async def f_move(req:FileMove,p:Principal=Depends(principal_dep)): return files.move(req.source,req.destination,p,req.overwrite)

    # Progressive search sessions: start -> page -> stop/list.
    @app.post('/api/v1/searches')
    async def search_start(req:SearchStart,p:Principal=Depends(principal_dep)):
        return await searches.start(p,req.root,req.pattern,req.search_type,req.file_pattern,req.ignore_case,req.include_hidden,req.max_results,req.literal)
    @app.get('/api/v1/searches')
    async def search_list(p:Principal=Depends(principal_dep)):
        require(p,'file.read'); return searches.list(p.name)
    @app.get('/api/v1/searches/{sid}')
    async def search_read(sid:str,offset:int=0,length:int=100,p:Principal=Depends(principal_dep)):
        require(p,'file.read'); return searches.read(sid,p.name,offset,length)
    @app.delete('/api/v1/searches/{sid}')
    async def search_stop(sid:str,p:Principal=Depends(principal_dep)):
        require(p,'file.read'); return await searches.stop(sid,p.name)

    @app.get('/api/v1/processes')
    async def processes(p:Principal=Depends(principal_dep)): return system.processes(p)
    @app.delete('/api/v1/processes/{pid}')
    async def kill(pid:int,p:Principal=Depends(principal_dep)): return system.kill(pid,p)
    @app.post('/api/v1/services')
    async def service(req:ServiceAction,p:Principal=Depends(principal_dep)): return await services.action(req.action,req.name,p)

    @app.post('/api/v1/terminal')
    async def terminal_start(req:TerminalStart,p:Principal=Depends(principal_dep)):
        require(p,'shell.write' if req.interactive else 'shell.read'); s=await terms.start(p.name,req.command,req.shell,req.cwd,req.interactive); return {'session_id':s.id,'pid':s.process.pid,'interactive':s.interactive}
    @app.get('/api/v1/terminal')
    async def terminal_list(p:Principal=Depends(principal_dep)):
        require(p,'shell.read'); return terms.list(p.name)
    @app.get('/api/v1/terminal/{sid}')
    async def terminal_read(sid:str,cursor:int=0,limit:int=200,p:Principal=Depends(principal_dep)): return terms.read(sid,p.name,cursor,limit)
    @app.post('/api/v1/terminal/{sid}/write')
    async def terminal_write(sid:str,req:TerminalWrite,p:Principal=Depends(principal_dep)):
        require(p,'shell.write'); return await terms.write(sid,p.name,req.data)
    @app.delete('/api/v1/terminal/{sid}')
    async def terminal_close(sid:str,p:Principal=Depends(principal_dep)): return await terms.close(sid,p.name)

    @app.get('/api/v1/desktop/observe')
    async def observe(include_image:bool=False,ocr:bool=False,p:Principal=Depends(principal_dep)): return desktop.observe(p,include_image,ocr)
    @app.get('/api/v1/desktop/tree')
    async def tree(title_re:str='.*',p:Principal=Depends(principal_dep)): return desktop.tree(p,title_re)
    @app.post('/api/v1/desktop/act')
    async def act(req:DesktopAct,p:Principal=Depends(principal_dep)): return desktop.act(p,req)
    @app.get('/api/v1/desktop/windows')
    async def native_windows(p:Principal=Depends(principal_dep)): return desktop.native_windows(p)
    @app.post('/api/v1/desktop/window')
    async def window_control(req:WindowControl,p:Principal=Depends(principal_dep)): return desktop.window_control(p,req.hwnd,req.action,x=req.x,y=req.y,w=req.w,h=req.h)
    @app.post('/api/v1/desktop/uia/find')
    async def uia_find(req:UIAFind,p:Principal=Depends(principal_dep)): return desktop.uia_find(p,req.title_re,req.name,req.control_type)
    @app.post('/api/v1/desktop/uia/invoke')
    async def uia_invoke(req:UIAInvoke,p:Principal=Depends(principal_dep)): return desktop.uia_invoke(p,req.title_re,req.name,req.automation_id)

    @app.get('/api/v1/clipboard')
    async def cb_get(p:Principal=Depends(principal_dep)): return clipboard.get(p)
    @app.post('/api/v1/clipboard')
    async def cb_set(req:ClipboardSet,p:Principal=Depends(principal_dep)): return clipboard.set(p,req.text)

    # 3.2 rich document plugin
    @app.get('/api/v1/documents/capabilities')
    def doc_caps(p:Principal=Depends(principal_dep)):
        require(p,'document.read'); return documents.capabilities()
    @app.post('/api/v1/documents/xlsx/read')
    def xlsx_read(req:XlsxRead,p:Principal=Depends(principal_dep)): return documents.xlsx_read(req.path,p,req.sheet,req.cell_range,req.formulas)
    @app.post('/api/v1/documents/xlsx/set-range')
    def xlsx_write(req:XlsxWrite,p:Principal=Depends(principal_dep)): return documents.xlsx_set_range(req.path,p,req.sheet,req.start_cell,req.values,req.create)
    @app.post('/api/v1/documents/xlsx/append')
    def xlsx_append(req:XlsxAppend,p:Principal=Depends(principal_dep)): return documents.xlsx_append_rows(req.path,p,req.sheet,req.values)
    @app.post('/api/v1/documents/docx/read')
    def docx_read(req:FilePath,p:Principal=Depends(principal_dep)): return documents.docx_read(req.path,p)
    @app.post('/api/v1/documents/docx/create')
    def docx_create(req:DocxCreate,p:Principal=Depends(principal_dep)): return documents.docx_create(req.path,p,req.paragraphs,req.title)
    @app.post('/api/v1/documents/docx/replace')
    def docx_replace(req:DocxReplace,p:Principal=Depends(principal_dep)): return documents.docx_replace(req.path,p,req.old,req.new,req.expected)
    @app.post('/api/v1/documents/pdf/read')
    def pdf_read(req:PdfRead,p:Principal=Depends(principal_dep)): return documents.pdf_read(req.path,p,req.start_page,req.pages)
    @app.post('/api/v1/documents/pdf/merge')
    def pdf_merge(req:PdfMerge,p:Principal=Depends(principal_dep)): return documents.pdf_merge(req.inputs,req.output,p)

    # Browser DevTools Protocol - native browser control before GUI fallback.
    @app.get('/api/v1/browser/status')
    async def browser_status(p:Principal=Depends(principal_dep)): return await browser.status(p)
    @app.get('/api/v1/browser/tabs')
    async def browser_tabs(p:Principal=Depends(principal_dep)): return await browser.tabs(p)
    @app.post('/api/v1/browser/evaluate')
    async def browser_eval(req:BrowserEval,p:Principal=Depends(principal_dep)): return await browser.evaluate(p,req.target_id,req.expression)
    @app.post('/api/v1/browser/navigate')
    async def browser_nav(req:BrowserNavigate,p:Principal=Depends(principal_dep)): return await browser.navigate(p,req.target_id,req.url)
    @app.get('/api/v1/browser/{target_id}/snapshot')
    async def browser_snapshot(target_id:str,p:Principal=Depends(principal_dep)): return await browser.snapshot(p,target_id)
    @app.get('/api/v1/browser/{target_id}/screenshot')
    async def browser_screenshot(target_id:str,format:str='png',quality:int=90,p:Principal=Depends(principal_dep)): return await browser.screenshot(p,target_id,format,quality)
    @app.post('/api/v1/browser/click')
    async def browser_click(req:BrowserSelector,p:Principal=Depends(principal_dep)): return await browser.click(p,req.target_id,req.selector)
    @app.post('/api/v1/browser/type')
    async def browser_type(req:BrowserType,p:Principal=Depends(principal_dep)): return await browser.type_text(p,req.target_id,req.selector,req.text,req.clear)
    @app.post('/api/v1/browser/tabs/new')
    async def browser_new_tab(req:BrowserNewTab,p:Principal=Depends(principal_dep)): return await browser.new_tab(p,req.url)
    @app.delete('/api/v1/browser/tabs/{target_id}')
    async def browser_close_tab(target_id:str,p:Principal=Depends(principal_dep)): return await browser.close_tab(p,target_id)

    # Windows Office COM. Optional and disabled by platform when unavailable.
    @app.get('/api/v1/office/status')
    def office_status(p:Principal=Depends(principal_dep)):
        require(p,'office.read'); return office.status(p)
    @app.post('/api/v1/office/excel/read')
    def office_excel_read(req:OfficeExcelRead,p:Principal=Depends(principal_dep)): return office.excel_read(p,req.workbook,req.sheet,req.cell_range)
    @app.post('/api/v1/office/excel/write')
    def office_excel_write(req:OfficeExcelWrite,p:Principal=Depends(principal_dep)): return office.excel_write(p,req.workbook,req.sheet,req.cell_range,req.value,req.save)
    @app.post('/api/v1/office/excel/format')
    def office_excel_format(req:OfficeExcelFormat,p:Principal=Depends(principal_dep)): return office.excel_format(p,req.workbook,req.sheet,req.cell_range,req.formatting)
    @app.post('/api/v1/office/word/read')
    def office_word_read(req:OfficeWordRead,p:Principal=Depends(principal_dep)): return office.word_text(p,req.document)
    @app.post('/api/v1/office/word/replace')
    def office_word_replace(req:OfficeWordReplace,p:Principal=Depends(principal_dep)): return office.word_replace(p,req.document,req.old,req.new)
    @app.post('/api/v1/office/word/insert-table')
    def office_word_table(req:OfficeWordTable,p:Principal=Depends(principal_dep)): return office.word_insert_table(p,req.document,req.rows,req.at_end)
    @app.post('/api/v1/office/powerpoint/read')
    def office_ppt_read(req:OfficePptRead,p:Principal=Depends(principal_dep)): return office.powerpoint_read(p,req.presentation)
    @app.post('/api/v1/office/powerpoint/add-text-slide')
    def office_ppt_slide(req:OfficePptAddSlide,p:Principal=Depends(principal_dep)): return office.powerpoint_add_text_slide(p,req.presentation,req.title,req.body,req.save_as)

    @app.get('/api/v1/desktop/graph')
    def desktop_graph_get(title_re:str='.*',include_ocr:bool=False,p:Principal=Depends(principal_dep)): return desktop_graph.build(p,title_re,include_ocr)

    @app.get('/api/v1/audit')
    async def audit_tail(n:int=200,p:Principal=Depends(principal_dep)):
        require(p,'audit.read'); return audit.tail(min(n,1000))
    @app.get('/api/v1/history')
    async def recent_history(limit:int=100,tool:str|None=None,p:Principal=Depends(principal_dep)):
        require(p,'audit.read'); return history.recent(limit,tool,None if p.allowed('*') else p.name)
    @app.get('/api/v1/usage')
    async def usage(p:Principal=Depends(principal_dep)):
        require(p,'audit.read'); return history.usage(None if p.allowed('*') else p.name)
    @app.get('/api/v1/config')
    async def config_view(p:Principal=Depends(principal_dep)):
        require(p,'config.read'); return settings.view()
    @app.post('/api/v1/config')
    async def config_set(req:ConfigSet,p:Principal=Depends(principal_dep)):
        require(p,'config.write')
        try:
            return settings.set(req.key,req.value)
        except (KeyError,ValueError) as e:
            raise HTTPException(400,str(e))

    if mcp is not None:
        def mp():
            pp=current_principal.get()
            if pp is None:
                # stdio transport has no HTTP auth middleware; the client is local and
                # holds config-file-level trust already, so grant the administrator scope.
                if os.getenv('AGENTNODE_MCP_TRANSPORT')=='stdio':
                    from .models import Role,ROLE_SCOPES
                    return Principal(name='local-stdio',role=Role('administrator'),scopes=ROLE_SCOPES[Role('administrator')])
                raise RuntimeError('authenticated MCP principal unavailable')
            return pp
        @mcp.tool()
        async def node_info(): return system.info(mp())
        @mcp.tool()
        async def shell_execute(command:str,shell_name:str|None=None,super_mode:bool=False,timeout_s:int=120):
            p=mp(); st=time.time(); req=ShellRequest(command=command,shell=shell_name,super_mode=super_mode,timeout_s=timeout_s)
            try:r=await shell.execute(req,p); rec('shell.execute',p,req.model_dump(),r,started=st,source='mcp'); return r
            except Exception as e: rec('shell.execute',p,req.model_dump(),error=str(e),started=st,source='mcp'); raise
        @mcp.tool()
        async def file_read(path:str,offset:int=0,length:int=1000): return files.read_smart(path,mp(),offset,length)
        @mcp.tool()
        async def file_read_multiple(paths:list[str],limit_per_file:int=1000): return files.read_many(paths,mp(),True,limit_per_file)
        @mcp.tool()
        async def file_write(path:str,data:str,atomic:bool=True,mode:str='rewrite'): return files.write(path,data,mp(),atomic,mode)
        @mcp.tool()
        async def file_info(path:str): return files.info(path,mp())
        @mcp.tool()
        async def file_replace(path:str,old:str,new:str,expected:int=1,fuzzy:bool=False,min_similarity:float=0.86,dry_run:bool=False): return files.replace(path,old,new,mp(),expected,fuzzy,min_similarity,dry_run)
        @mcp.tool()
        async def search_start(root:str,pattern:str,search_type:str='content',file_pattern:str|None=None,ignore_case:bool=True,include_hidden:bool=False,max_results:int=2000,literal:bool=False): return await searches.start(mp(),root,pattern,search_type,file_pattern,ignore_case,include_hidden,max_results,literal)
        @mcp.tool()
        async def search_read(session_id:str,offset:int=0,length:int=100): return searches.read(session_id,mp().name,offset,length)
        @mcp.tool()
        async def search_stop(session_id:str): return await searches.stop(session_id,mp().name)
        @mcp.tool()
        async def terminal_start(command:str,shell_name:str|None=None,cwd:str|None=None,interactive:bool=False):
            p=mp(); require(p,'shell.write' if interactive else 'shell.read'); s=await terms.start(p.name,command,shell_name,cwd,interactive); return {'session_id':s.id,'pid':s.process.pid,'interactive':s.interactive}
        @mcp.tool()
        async def terminal_read(session_id:str,cursor:int=0,limit:int=200): return terms.read(session_id,mp().name,cursor,limit)
        @mcp.tool()
        async def terminal_write(session_id:str,data:str):
            p=mp(); require(p,'shell.write'); return await terms.write(session_id,p.name,data)
        @mcp.tool()
        async def terminal_list():
            p=mp(); require(p,'shell.read'); return terms.list(p.name)
        @mcp.tool()
        async def terminal_close(session_id:str): return await terms.close(session_id,mp().name)
        @mcp.tool()
        async def code_execute(language:str,code:str,timeout_s:int=60,cwd:str|None=None): return await codeexec.run(mp(),language,code,timeout_s,cwd)
        @mcp.tool()
        async def job_list(limit:int=100):
            p=mp(); require(p,'job.read'); return [j.model_dump() for j in jobs.list(limit) if p.allowed('*') or j.owner==p.name]
        @mcp.tool()
        async def tool_history(limit:int=50,tool:str|None=None):
            p=mp(); require(p,'audit.read'); return history.recent(limit,tool,None if p.allowed('*') else p.name)
        @mcp.tool()
        async def desktop_observe(include_image:bool=False,ocr:bool=False): return desktop.observe(mp(),include_image,ocr)
        @mcp.tool()
        async def desktop_action(action:str,x:int|None=None,y:int|None=None,text:str|None=None,keys:list[str]|None=None,amount:int=0): return desktop.act(mp(),DesktopAct(action=action,x=x,y=y,text=text,keys=keys,amount=amount))
        @mcp.tool()
        async def desktop_graph_read(title_re:str='.*',include_ocr:bool=False): return await asyncio.to_thread(desktop_graph.build,mp(),title_re,include_ocr)
        @mcp.tool()
        def xlsx_read(path:str,sheet:str|None=None,cell_range:str|None=None,formulas:bool=True): return documents.xlsx_read(path,mp(),sheet,cell_range,formulas)
        @mcp.tool()
        async def xlsx_set_range(path:str,sheet:str,start_cell:str,values:list[list[Any]],create:bool=False): return await asyncio.to_thread(documents.xlsx_set_range,path,mp(),sheet,start_cell,values,create)
        @mcp.tool()
        async def xlsx_append_rows(path:str,sheet:str,values:list[list[Any]]): return await asyncio.to_thread(documents.xlsx_append_rows,path,mp(),sheet,values)
        @mcp.tool()
        async def docx_read(path:str): return await asyncio.to_thread(documents.docx_read,path,mp())
        @mcp.tool()
        async def docx_replace(path:str,old:str,new:str,expected:int|None=None): return await asyncio.to_thread(documents.docx_replace,path,mp(),old,new,expected)
        @mcp.tool()
        async def pdf_read(path:str,start_page:int=0,pages:int=20): return await asyncio.to_thread(documents.pdf_read,path,mp(),start_page,pages)
        @mcp.tool()
        async def pdf_merge(inputs:list[str],output:str): return await asyncio.to_thread(documents.pdf_merge,inputs,output,mp())
        @mcp.tool()
        async def office_excel_read(workbook:str,sheet:str,cell_range:str): return await asyncio.to_thread(office.excel_read,mp(),workbook,sheet,cell_range)
        @mcp.tool()
        async def office_excel_write(workbook:str,sheet:str,cell_range:str,value:Any,save:bool=True): return await asyncio.to_thread(office.excel_write,mp(),workbook,sheet,cell_range,value,save)
        @mcp.tool()
        async def office_word_read(document:str): return await asyncio.to_thread(office.word_text,mp(),document)
        @mcp.tool()
        async def office_word_replace(document:str,old:str,new:str): return await asyncio.to_thread(office.word_replace,mp(),document,old,new)
        @mcp.tool()
        async def office_powerpoint_read(presentation:str): return await asyncio.to_thread(office.powerpoint_read,mp(),presentation)
        @mcp.tool()
        async def office_powerpoint_add_text_slide(presentation:str,title:str,body:str,save_as:str|None=None): return await asyncio.to_thread(office.powerpoint_add_text_slide,mp(),presentation,title,body,save_as)
        @mcp.tool()
        async def browser_tabs(): return await browser.tabs(mp())
        @mcp.tool()
        async def browser_navigate(target_id:str,url:str): return await browser.navigate(mp(),target_id,url)
        @mcp.tool()
        async def browser_snapshot(target_id:str): return await browser.snapshot(mp(),target_id)
        @mcp.tool()
        async def browser_click(target_id:str,selector:str): return await browser.click(mp(),target_id,selector)
        @mcp.tool()
        async def browser_type(target_id:str,selector:str,text:str,clear:bool=True): return await browser.type_text(mp(),target_id,selector,text,clear)
        @mcp.tool()
        async def agent_run(prompt:str,cwd:str|None=None,runtime:str|None=None,timeout_s:int=1800):
            p=mp(); require(p,'agent.run'); j=jobs.create('agent',p.name,{'prompt':prompt,'cwd':cwd,'runtime':runtime})
            async def fn(job): return await runtimes.run(job,prompt,cwd,runtime,timeout_s)
            jobs.submit(j,fn); return j.model_dump()

        class MCPAuthASGI:
            def __init__(self,inner): self.inner=inner
            async def __call__(self,scope,receive,send):
                if scope.get('type')!='http': return await self.inner(scope,receive,send)
                # Bare /mcp (no trailing slash) enters without the mount prefix strip.
                if scope.get('path') in ('','/mcp'): scope=dict(scope,path='/')
                headers={k.decode().lower():v.decode() for k,v in scope.get('headers',[])}; value=headers.get('authorization','')
                if not value.lower().startswith('bearer '):
                    await send({'type':'http.response.start','status':401,'headers':[(b'content-type',b'application/json')]}); await send({'type':'http.response.body','body':b'{"detail":"Bearer token required"}'}); return
                try: pp=auth.authenticate(value.split(None,1)[1])
                except Exception:
                    await send({'type':'http.response.start','status':401,'headers':[(b'content-type',b'application/json')]}); await send({'type':'http.response.body','body':b'{"detail":"invalid token"}'}); return
                tok=current_principal.set(pp)
                try: await self.inner(scope,receive,send)
                finally: current_principal.reset(tok)
        app.mount('/mcp',MCPAuthASGI(mcp.streamable_http_app()))
        from starlette.routing import Route as StarletteRoute
        app.router.routes.append(StarletteRoute('/mcp',MCPAuthASGI(mcp.streamable_http_app()),methods=['GET','POST','DELETE']))
    return app
