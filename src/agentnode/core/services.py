from __future__ import annotations
import asyncio
from .auth import require
from ..models import Principal
from ..platform import get_platform_adapter
class ServiceManager:
    def __init__(self): self.platform=get_platform_adapter()
    async def action(self,action,name,p:Principal):
        require(p,'service.read' if action=='status' else 'service.write')
        spec=self.platform.service_command(action,name)
        proc=await asyncio.create_subprocess_exec(*spec.argv,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,creationflags=spec.creationflags,start_new_session=spec.start_new_session)
        out,err=await proc.communicate(); return {'exit_code':proc.returncode,'stdout':out.decode(errors='replace'),'stderr':err.decode(errors='replace')}
