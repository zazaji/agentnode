from __future__ import annotations
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field

class Role(str, Enum):
    viewer="viewer"; operator="operator"; developer="developer"; desktop="desktop"; administrator="administrator"; super="super"; node="node"

ROLE_SCOPES={
Role.viewer:{"node.read","job.read","audit.read"},
Role.operator:{"node.read","job.read","job.run","shell.read","file.read","document.read","process.read","service.read","browser.read"},
Role.developer:{"node.read","job.read","job.run","shell.read","shell.write","file.read","file.write","document.read","document.write","process.read","process.write","service.read","config.read","browser.read","browser.write"},
Role.desktop:{"node.read","job.read","desktop.observe","desktop.input","clipboard.read","clipboard.write","browser.read","browser.write"},
Role.administrator:{"node.read","job.read","job.run","shell.read","shell.write","file.read","file.write","document.read","document.write","process.read","process.write","service.read","service.write","desktop.observe","desktop.input","clipboard.read","clipboard.write","browser.read","browser.write","office.read","office.write","agent.run","mesh.delegate","config.read","config.write"},
Role.super:{"*"}, Role.node:{"node.read","job.read","job.run","mesh.delegate","agent.run"}}

class Principal(BaseModel):
    name:str; role:Role; scopes:set[str]=Field(default_factory=set)
    def allowed(self, scope:str)->bool: return "*" in self.scopes or scope in self.scopes

class JobState(str, Enum): queued="queued"; running="running"; succeeded="succeeded"; failed="failed"; cancelled="cancelled"; interrupted="interrupted"
class Job(BaseModel):
    id:str; kind:str; owner:str; state:JobState=JobState.queued; progress:int=0; phase:str="queued"; message:str=""; input:dict[str,Any]=Field(default_factory=dict); result:Any=None; error:str|None=None; trace_id:str|None=None; target_node:str|None=None; created_at:float; updated_at:float
class ShellRequest(BaseModel):
    command:str; shell:str|None=None; cwd:str|None=None; timeout_s:int=120; background:bool=False; super_mode:bool=False
    # Mesh delegation markers set by MeshRouter when this request was forwarded
    # from a peer. Their presence authorizes the action via mesh.delegate instead
    # of shell.read/shell.write, which is how a node-role peer token may execute.
    trace_id:str|None=None; hops:list[str]=Field(default_factory=list)
class AgentRequest(BaseModel):
    prompt:str; cwd:str|None=None; background:bool=True; runtime:str|None=None; timeout_s:int=1800
    trace_id:str|None=None; hops:list[str]=Field(default_factory=list)
class DelegateRequest(BaseModel):
    peer:str; action:Literal["shell","agent"]; payload:dict[str,Any]; trace_id:str|None=None; hops:list[str]=Field(default_factory=list)
class CoordinateTask(BaseModel):
    action:Literal["shell","agent"]; payload:dict[str,Any]
class CoordinateRequest(BaseModel):
    task:CoordinateTask; peers:list[str]|None=None; timeout_s:int=120; parallel:bool=True
    trace_id:str|None=None; hops:list[str]=Field(default_factory=list)
class ForwardPolicyOverride(BaseModel):
    mode:str|None=None; offload_after:int|None=None; max_forwards:int|None=None
class ForwardRequest(BaseModel):
    # task relay (转交): a node forwards the task to another node instead of (or
    # instead of only) executing it. forwardable=False marks a task that must not
    # be re-forwarded: the first hand-off is still allowed, but the receiving node
    # then executes locally. hops is the visited path; a forward target may never
    # be a node already on that path (never hand back to upstream).
    task:CoordinateTask; target:str|None=None
    forwardable:bool=True; policy:ForwardPolicyOverride|None=None
    trace_id:str|None=None; hops:list[str]=Field(default_factory=list)
    forwards_left:int|None=None           # None -> use effective policy max_forwards
class DesktopAct(BaseModel):
    action:Literal["click","double_click","right_click","move","scroll","type_text","hotkey"]; x:int|None=None; y:int|None=None; text:str|None=None; keys:list[str]|None=None; amount:int=0
