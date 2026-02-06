class WebSocketRejectMiddleware:
    """Reject websocket connections unless explicitly enabled."""

    def __init__(self, app, enabled: bool = False):
        self.app = app
        self.enabled = enabled

    async def __call__(self, scope, receive, send):
        if scope.get('type') == 'websocket' and not self.enabled:
            await send({'type': 'websocket.close', 'code': 1008})
            return
        await self.app(scope, receive, send)
