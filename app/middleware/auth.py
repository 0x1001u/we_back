from typing import Optional, Callable
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.models.database import get_db, User
from app.models.schemas import TokenData, WechatHeaders
from app.utils.jwt import jwt_manager
from app.services.user_service import UserService
import json

security = HTTPBearer()


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """获取当前用户（微信云托管方式）"""
    try:
        # 从请求头获取微信用户信息
        openid = request.headers.get("X-WX-OPENID")
        if not openid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing WeChat user information"
            )
        
        # 查找用户
        user_service = UserService(db)
        user = user_service.get_user_by_openid(openid)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User is not active"
            )
        
        return user
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


async def get_current_user_with_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """获取当前用户（JWT令牌方式）"""
    try:
        # 验证JWT令牌
        token_data = jwt_manager.verify_token(credentials.credentials)
        
        if not token_data.user_id and not token_data.openid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # 查找用户
        user_service = UserService(db)
        
        if token_data.user_id:
            user = user_service.get_user_by_id(token_data.user_id)
        else:
            user = user_service.get_user_by_openid(token_data.openid)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User is not active"
            )
        
        # 验证用户会话
        if not user_service.validate_user_session(user.id, credentials.credentials):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session"
            )
        
        return user
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


async def get_wechat_headers(request: Request) -> WechatHeaders:
    """获取微信云托管请求头"""
    try:
        headers = WechatHeaders(
            x_wx_openid=request.headers.get("X-WX-OPENID", ""),
            x_wx_appid=request.headers.get("X-WX-APPID", ""),
            x_wx_unionid=request.headers.get("X-WX-UNIONID"),
            x_wx_from_openid=request.headers.get("X-WX-FROM-OPENID"),
            x_wx_from_appid=request.headers.get("X-WX-FROM-APPID"),
            x_wx_from_unionid=request.headers.get("X-WX-FROM-UNIONID"),
            x_wx_env=request.headers.get("X-WX-ENV"),
            x_wx_source=request.headers.get("X-WX-SOURCE"),
            x_forwarded_for=request.headers.get("X-Forwarded-For")
        )
        
        if not headers.x_wx_openid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-WX-OPENID header"
            )
        
        return headers
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid WeChat headers: {str(e)}"
        )


def get_client_ip(request: Request) -> str:
    """获取客户端IP地址"""
    # 优先从X-Forwarded-For获取
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    
    # 其次从X-Real-IP获取
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        return x_real_ip
    
    # 最后从连接信息获取
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    """获取用户代理"""
    return request.headers.get("User-Agent", "unknown")


def require_auth(auth_type: str = "wechat") -> Callable:
    """权限校验装饰器"""
    def decorator(func: Callable) -> Callable:
        if auth_type == "wechat":
            # 微信云托管认证
            async def wechat_auth_wrapper(
                request: Request,
                current_user: User = Depends(get_current_user),
                *args, **kwargs
            ):
                # 将请求信息添加到kwargs中
                kwargs["request"] = request
                kwargs["current_user"] = current_user
                kwargs["client_ip"] = get_client_ip(request)
                kwargs["user_agent"] = get_user_agent(request)
                return await func(*args, **kwargs)
            
            return wechat_auth_wrapper
        
        elif auth_type == "jwt":
            # JWT令牌认证
            async def jwt_auth_wrapper(
                request: Request,
                current_user: User = Depends(get_current_user_with_token),
                *args, **kwargs
            ):
                # 将请求信息添加到kwargs中
                kwargs["request"] = request
                kwargs["current_user"] = current_user
                kwargs["client_ip"] = get_client_ip(request)
                kwargs["user_agent"] = get_user_agent(request)
                return await func(*args, **kwargs)
            
            return jwt_auth_wrapper
        
        else:
            raise ValueError(f"Unsupported auth type: {auth_type}")
    
    return decorator


def require_admin() -> Callable:
    """管理员权限校验装饰器"""
    def decorator(func: Callable) -> Callable:
        async def admin_wrapper(
            current_user: User = Depends(get_current_user),
            *args, **kwargs
        ):
            # 这里可以根据实际需求添加管理员权限校验逻辑
            # 例如：检查用户是否有管理员角色
            if not current_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User is not active"
                )
            
            return await func(*args, **kwargs)
        
        return admin_wrapper
    
    return decorator


def log_request() -> Callable:
    """请求日志装饰器"""
    def decorator(func: Callable) -> Callable:
        async def log_wrapper(
            request: Request,
            *args, **kwargs
        ):
            # 记录请求信息
            client_ip = get_client_ip(request)
            user_agent = get_user_agent(request)
            method = request.method
            url = str(request.url)
            
            # 这里可以添加日志记录逻辑
            print(f"Request: {method} {url} - IP: {client_ip} - User-Agent: {user_agent}")
            
            return await func(*args, **kwargs)
        
        return log_wrapper
    
    return decorator