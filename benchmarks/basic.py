import asyncio,time
from agentnode.core.config import AppConfig
from agentnode.core.shell import ShellRunner
from agentnode.models import Principal,Role,ROLE_SCOPES,ShellRequest
async def main(n=20):
    p=Principal(name='bench',role=Role.super,scopes=ROLE_SCOPES[Role.super]); r=ShellRunner(AppConfig()); t=time.perf_counter()
    for _ in range(n): await r.execute(ShellRequest(command='echo ok'),p)
    print({'runs':n,'seconds':time.perf_counter()-t})
if __name__=='__main__':asyncio.run(main())
