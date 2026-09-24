from __future__ import annotations
import asyncio, os, secrets, uuid, httpx
from ..models import DelegateRequest, CoordinateRequest, ForwardRequest, Principal
from ..core.auth import require

class MeshRouter:
    def __init__(self,cfg):
        self.cfg=cfg
        self.local_executor=None            # async (action,payload,trace_id,hops,forwardable)->response
        self._active=0                      # in-flight forward requests handled by this node
        self._inflight:dict[str,int]={}     # in-flight forwards dispatched to each peer
    def peers(self): return {k:{"url":v.get('url'),"token_configured":bool(v.get('token') or v.get('token_env'))} for k,v in self.cfg.mesh.peers.items()}
    def _check_trace(self,hops:list[str]):
        nid=self.cfg.mesh.node_id
        if nid in hops: raise ValueError('mesh loop detected')
        hops=[*hops,nid]
        if len(hops)>self.cfg.mesh.max_hops: raise ValueError('max hops exceeded')
        return hops
    def _require_helper(self,presented_key:str|None):
        """A node only acts as an auxiliary (helper) node if it holds the shared key,
        and requires the caller to present that same key (constant-time compare)."""
        key=self.cfg.mesh.helper_key
        if not key: raise PermissionError('this node is not an auxiliary (helper) node')
        if not presented_key or not secrets.compare_digest(presented_key,key):
            raise PermissionError('invalid or missing auxiliary helper key')
    def _mode(self,req:ForwardRequest): return req.policy.mode if (req.policy and req.policy.mode) else self.cfg.mesh.forward_policy.mode
    def _offload_after(self,req:ForwardRequest): return req.policy.offload_after if (req.policy and req.policy.offload_after is not None) else self.cfg.mesh.forward_policy.offload_after
    def _forwards_left(self,req:ForwardRequest):
        if req.forwards_left is not None: return req.forwards_left
        if req.policy and req.policy.max_forwards is not None: return req.policy.max_forwards
        return self.cfg.mesh.forward_policy.max_forwards
    def _peer_node_id(self,name:str)->str:
        # A peer may declare its node identity (peers.<name>.node_id). The visited
        # path stores node_ids, so upstream checks must compare against that, not
        # just the peer's local config key (a peer can be named anything).
        return (self.cfg.mesh.peers.get(name) or {}).get('node_id') or name
    def _is_upstream(self,name:str,path:list[str])->bool:
        return name in path or self._peer_node_id(name) in path
    def _pick_target(self,mode:str,offload_after:int,path:list[str])->str|None:
        # Never pick a node already on the path: that node is upstream (a parent or
        # transitive ancestor) and handing the task back to it would start a loop.
        candidates=[n for n in self.cfg.mesh.peers if not self._is_upstream(n,path)]
        if not candidates: return None
        if mode=='distribute':
            return min(candidates,key=lambda n:self._inflight.get(n,0))
        if mode=='offload':
            if offload_after<=0 or self._active<=offload_after: return None
            return min(candidates,key=lambda n:self._inflight.get(n,0))
        return None
    async def _invoke(self,peer_name:str,action:str,payload:dict,trace_id:str,hops:list[str],timeout_s:float=60):
        peer=self.cfg.mesh.peers.get(peer_name)
        if not peer: raise KeyError(f'unknown peer: {peer_name}')
        token=peer.get('token') or os.getenv(peer.get('token_env',''))
        if not token: raise RuntimeError('peer token not configured')
        endpoint='/api/v1/shell' if action=='shell' else '/api/v1/agent'
        body=dict(payload); body['trace_id']=trace_id; body['hops']=hops
        async with httpx.AsyncClient(timeout=timeout_s) as c:
            r=await c.post(peer['url'].rstrip('/')+endpoint,json=body,headers={'Authorization':f'Bearer {token}'})
            r.raise_for_status(); return r.json()
    async def _invoke_forward(self,peer_name:str,req:ForwardRequest,trace_id:str,hops:list[str],forwards_left:int,timeout_s:float=60):
        peer=self.cfg.mesh.peers.get(peer_name)
        if not peer: raise KeyError(f'unknown peer: {peer_name}')
        token=peer.get('token') or os.getenv(peer.get('token_env',''))
        if not token: raise RuntimeError('peer token not configured')
        body={'task':req.task.model_dump(),'target':None,'forwardable':req.forwardable,
              'policy':req.policy.model_dump() if req.policy else None,
              'trace_id':trace_id,'hops':hops,'forwards_left':forwards_left}
        headers={'Authorization':f'Bearer {token}','X-AgentNode-Helper-Key':self.cfg.mesh.helper_key}
        async with httpx.AsyncClient(timeout=timeout_s) as c:
            r=await c.post(peer['url'].rstrip('/')+'/api/v1/mesh/forward',json=body,headers=headers)
            r.raise_for_status(); return r.json()
    async def _run_local(self,action:str,payload:dict,trace_id:str|None,hops:list[str],forwardable:bool):
        if self.local_executor is None: raise RuntimeError('no local executor configured')
        return await self.local_executor(action,payload,trace_id,hops,forwardable)
    async def _execute_local(self,req:ForwardRequest,path:list[str]):
        trace=req.trace_id or uuid.uuid4().hex
        try: resp=await self._run_local(req.task.action,dict(req.task.payload),trace,path,req.forwardable)
        except Exception as e:
            resp={'error':str(e)}
        return {'trace_id':trace,'node_id':self.cfg.mesh.node_id,'action':req.task.action,
                'forwarded_to':None,'hops':path,'response':resp}
    async def forward(self,p:Principal,req:ForwardRequest,presented_key:str|None=None):
        require(p,'mesh.delegate'); self._require_helper(presented_key)
        prior_path=list(req.hops); is_origin=not prior_path
        path=self._check_trace(req.hops)
        trace=req.trace_id or uuid.uuid4().hex
        self._active+=1
        try:
            if not is_origin and not req.forwardable:
                # This node received a task that must not be re-forwarded: execute here.
                return await self._execute_local(req,path)
            if is_origin and not req.forwardable and not req.target:
                # Marked "do not re-transfer" with no explicit hand-off target: just run.
                return await self._execute_local(req,path)
            if req.target:
                if self._is_upstream(req.target,path):
                    raise ValueError(f'refusing to forward back to upstream node "{req.target}"')
                return await self._forward_to(req,trace,path,req.target)
            if self._forwards_left(req)<=0:
                # Relay budget exhausted: execute locally instead of forwarding again.
                return await self._execute_local(req,path)
            target=self._pick_target(self._mode(req),self._offload_after(req),path)
            if target is None:
                return await self._execute_local(req,path)
            return await self._forward_to(req,trace,path,target)
        finally:
            self._active-=1
    async def _forward_to(self,req:ForwardRequest,trace:str,path:list[str],target:str):
        self._inflight[target]=self._inflight.get(target,0)+1
        try:
            resp=await self._invoke_forward(target,req,trace,path,self._forwards_left(req)-1)
        except Exception as e:
            resp={'error':str(e)}
        finally:
            self._inflight[target]=max(0,self._inflight.get(target,0)-1)
        return {'trace_id':trace,'node_id':self.cfg.mesh.node_id,'action':req.task.action,
                'forwarded_to':target,'hops':path,'response':resp}
    async def delegate(self,p:Principal,req:DelegateRequest):
        require(p,'mesh.delegate'); hops=self._check_trace(req.hops)
        trace=req.trace_id or uuid.uuid4().hex
        resp=await self._invoke(req.peer,req.action,req.payload,trace,hops)
        return {'trace_id':trace,'peer':req.peer,'response':resp}
    async def coordinate(self,p:Principal,req:CoordinateRequest):
        require(p,'mesh.delegate'); hops=self._check_trace(req.hops)
        trace=req.trace_id or uuid.uuid4().hex
        unknown=[k for k in (req.peers or []) if k not in self.cfg.mesh.peers]
        # Exclude any node already on the path: subtasks (or a relayed context) may
        # never be handed back to an upstream node -- that would close a loop.
        targets=[n for n in self.cfg.mesh.peers if not self._is_upstream(n,hops) and (req.peers is None or n in req.peers)]
        results={}
        async def one(name:str):
            try:
                resp=await asyncio.wait_for(self._invoke(name,req.task.action,dict(req.task.payload),trace,hops,req.timeout_s),timeout=req.timeout_s)
                results[name]={'ok':True,'trace_id':trace,'response':resp}
            except asyncio.TimeoutError:
                results[name]={'ok':False,'trace_id':trace,'error':'timeout'}
            except Exception as e:
                results[name]={'ok':False,'trace_id':trace,'error':str(e)}
        tasks=[asyncio.create_task(one(n)) for n in targets]
        if req.parallel: await asyncio.gather(*tasks)
        else:
            for t in tasks: await t
        return {'trace_id':trace,'coordinator':self.cfg.mesh.node_id,'parallel':req.parallel,
                'targets':targets,'unknown':unknown,'results':results}
