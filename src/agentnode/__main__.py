import argparse, os
from .core.config import init_config

def main():
    ap=argparse.ArgumentParser('agentnode'); sp=ap.add_subparsers(dest='cmd')
    run=sp.add_parser('serve'); run.add_argument('--config',default=os.getenv('AGENTNODE_CONFIG','config.yaml')); run.add_argument('--host'); run.add_argument('--port',type=int)
    stdio=sp.add_parser('mcp-stdio'); stdio.add_argument('--config',default=os.getenv('AGENTNODE_CONFIG','config.yaml'))
    init=sp.add_parser('init'); init.add_argument('--config',default='config.yaml')
    co=sp.add_parser('mesh-coordinate'); co.add_argument('--url',default=os.getenv('AGENTNODE_URL','http://127.0.0.1:8765')); co.add_argument('--token-env',default=os.getenv('AGENTNODE_ADMIN_TOKEN_ENV','AGENTNODE_ADMIN_TOKEN')); co.add_argument('--peer',action='append'); co.add_argument('--tool',choices=['shell','agent'],default='shell'); co.add_argument('--payload'); co.add_argument('--command'); co.add_argument('--prompt'); co.add_argument('--timeout',type=int,default=120); co.add_argument('--sequential',action='store_true')
    fw=sp.add_parser('mesh-forward'); fw.add_argument('--url',default=os.getenv('AGENTNODE_URL','http://127.0.0.1:8765')); fw.add_argument('--token-env',default=os.getenv('AGENTNODE_ADMIN_TOKEN_ENV','AGENTNODE_ADMIN_TOKEN')); fw.add_argument('--helper-key-env',default=os.getenv('AGENTNODE_HELPER_KEY_ENV','AGENTNODE_HELPER_KEY')); fw.add_argument('--target'); fw.add_argument('--tool',choices=['shell','agent'],default='shell'); fw.add_argument('--payload'); fw.add_argument('--command'); fw.add_argument('--prompt'); fw.add_argument('--no-forwardable',action='store_true'); fw.add_argument('--mode',choices=['off','offload','distribute']); fw.add_argument('--max-forwards',type=int); fw.add_argument('--timeout',type=int,default=120)
    desk=sp.add_parser('desktop-worker'); desk.add_argument('--config',default='config.yaml')
    args=ap.parse_args()
    if args.cmd=='init':
        _,tokens=init_config(args.config); print('TOKENS (shown once):'); [print(f'{k}: {v}') for k,v in tokens.items()]; return
    if args.cmd=='desktop-worker':
        from .desktop.worker import main as dm; import sys; sys.argv=[sys.argv[0],'--config',args.config]; dm(); return
    if args.cmd=='mcp-stdio':
        os.environ['AGENTNODE_CONFIG']=args.config
        os.environ['AGENTNODE_MCP_TRANSPORT']='stdio'
        from .app import create_app
        app=create_app(args.config); mcp=app.state.ctx.get('mcp')
        if mcp is None: raise SystemExit("MCP SDK is not installed. Install: pip install 'agentnode[mcp]'")
        mcp.run(transport='stdio'); return
    if args.cmd=='mesh-coordinate':
        import json as _json, httpx
        token=os.getenv(args.token_env)
        if not token: raise SystemExit(f'{args.token_env} is not set; export the operator/super/node token that has mesh.delegate scope')
        if args.payload: payload=_json.loads(args.payload)
        elif args.tool=='shell': payload={'command':args.command or ''}
        elif args.tool=='agent': payload={'prompt':args.prompt or ''}
        else: payload={}
        body={'task':{'action':args.tool,'payload':payload},'peers':args.peer,'timeout_s':args.timeout,'parallel':not args.sequential}
        r=httpx.post(args.url.rstrip('/')+'/api/v1/mesh/coordinate',json=body,headers={'Authorization':f'Bearer {token}'},timeout=args.timeout+15)
        r.raise_for_status(); data=r.json()
        print(f"trace {data['trace_id']}  coordinator {data['coordinator']}  parallel {data['parallel']}")
        print(f"targets {data['targets']}  unknown {data['unknown']}")
        for name,res in data['results'].items():
            if res['ok']: print(f"ok    {name:<14} {str(res['response'])[:200]}")
            else:         print(f"FAIL  {name:<14} {res['error']}")
        fails=[n for n,v in data['results'].items() if not v['ok']]
        raise SystemExit(1 if fails else 0)
    if args.cmd=='mesh-forward':
        import json as _json, httpx
        token=os.getenv(args.token_env); helper=os.getenv(args.helper_key_env)
        if not token: raise SystemExit(f'{args.token_env} is not set; export the operator/super/node token that has mesh.delegate scope')
        if not helper: raise SystemExit(f'{args.helper_key_env} is not set; the shared auxiliary helper key is required for task relay')
        if args.payload: payload=_json.loads(args.payload)
        elif args.tool=='shell': payload={'command':args.command or ''}
        elif args.tool=='agent': payload={'prompt':args.prompt or ''}
        else: payload={}
        body={'task':{'action':args.tool,'payload':payload},'target':args.target,'forwardable':not args.no_forwardable,'forwards_left':args.max_forwards}
        if args.mode: body['policy']={'mode':args.mode}
        headers={'Authorization':f'Bearer {token}','X-AgentNode-Helper-Key':helper}
        r=httpx.post(args.url.rstrip('/')+'/api/v1/mesh/forward',json=body,headers=headers,timeout=args.timeout+15)
        r.raise_for_status(); data=r.json()
        print(f"trace {data['trace_id']}  node {data['node_id']}  action {data['action']}  forwarded_to {data['forwarded_to']}  via {data['hops']}")
        print(f"response: {str(data['response'])[:400]}")
        return
    from .core.config import load_config
    cfg=load_config(args.config if hasattr(args,'config') else 'config.yaml'); os.environ['AGENTNODE_CONFIG']=args.config if hasattr(args,'config') else 'config.yaml'
    import uvicorn
    uvicorn.run('agentnode.app:create_app',factory=True,host=getattr(args,'host',None) or cfg.host,port=getattr(args,'port',None) or cfg.port)
if __name__=='__main__':main()
