from __future__ import annotations


class BodyLimitMiddleware:
    """ASGI body-size limiter that handles Content-Length and chunked bodies."""
    def __init__(self, app, max_bytes:int):
        self.app=app; self.max_bytes=max(1,int(max_bytes))

    async def __call__(self,scope,receive,send):
        if scope.get('type')!='http':
            return await self.app(scope,receive,send)
        headers={k.lower():v for k,v in scope.get('headers',[])}
        raw=headers.get(b'content-length')
        if raw:
            try:
                if int(raw)>self.max_bytes:
                    return await self._reject(send)
            except ValueError: pass
        total=0; rejected=False
        async def limited_receive():
            nonlocal total,rejected
            msg=await receive()
            if msg.get('type')=='http.request':
                total+=len(msg.get('body',b''))
                if total>self.max_bytes:
                    rejected=True
                    # Drain semantics are handled by returning an empty terminal body
                    # to the downstream app, but the outer wrapper will suppress its output.
                    return {'type':'http.request','body':b'','more_body':False}
            return msg
        sent_start=False
        async def guarded_send(message):
            nonlocal sent_start
            if rejected: return
            if message.get('type')=='http.response.start': sent_start=True
            await send(message)
        await self.app(scope,limited_receive,guarded_send)
        if rejected and not sent_start:
            await self._reject(send)

    @staticmethod
    async def _reject(send):
        body=b'{"detail":"request body too large"}'
        await send({'type':'http.response.start','status':413,'headers':[(b'content-type',b'application/json'),(b'content-length',str(len(body)).encode())]})
        await send({'type':'http.response.body','body':body})


class SecurityHeadersMiddleware:
    def __init__(self,app): self.app=app
    async def __call__(self,scope,receive,send):
        if scope.get('type')!='http': return await self.app(scope,receive,send)
        async def wrapped_send(message):
            if message.get('type')=='http.response.start':
                headers=list(message.get('headers',[]))
                headers.extend([
                    (b'x-content-type-options',b'nosniff'),
                    (b'x-frame-options',b'DENY'),
                    (b'referrer-policy',b'no-referrer'),
                    (b'permissions-policy',b'camera=(), microphone=(), geolocation=()'),
                ])
                message['headers']=headers
            await send(message)
        await self.app(scope,receive,wrapped_send)
