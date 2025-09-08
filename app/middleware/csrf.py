import os
import binascii
from typing import Callable
from starlette.requests import Request
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint

class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exempt_methods=["GET", "HEAD", "OPTIONS"], exempt_paths=None):
        super().__init__(app)
        self.exempt_methods = exempt_methods
        self.exempt_paths = exempt_paths or []
        self.token_length = 32
        
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        # 跳过豁免的路径
        if request.url.path in self.exempt_paths:
            return await call_next(request)
            
        # 跳过豁免的HTTP方法
        if request.method in self.exempt_methods:
            return await call_next(request)
            
        # 从cookie和header获取令牌
        csrf_cookie = request.cookies.get("csrftoken")
        csrf_header = request.headers.get("x-csrf-token")
        
        # 验证令牌 - 允许首次登录场景（cookie和header都为空）
        is_first_login = not csrf_cookie and not csrf_header
        if not is_first_login and (not csrf_cookie or not csrf_header or csrf_cookie != csrf_header):
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid CSRF token"
            )
            
        response = await call_next(request)
        
        # 为新会话设置CSRF令牌
        if not csrf_cookie and hasattr(request.state, "user"):
            token = binascii.hexlify(os.urandom(self.token_length)).decode()
            response.set_cookie(
                key="csrftoken",
                value=token,
                httponly=False,
                samesite="strict",
                secure=True
            )
            
        return response