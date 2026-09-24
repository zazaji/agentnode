from contextvars import ContextVar
from ..models import Principal
current_principal: ContextVar[Principal|None] = ContextVar('agentnode_principal', default=None)
