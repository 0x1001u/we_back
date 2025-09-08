from datetime import datetime, timedelta
from typing import Optional, Union, Any
from jose import JWTError, jwt
from fastapi import HTTPException, status
from app.config import settings
from app.models.schemas import TokenData


class JWTManager:
    """JWT令牌管理器"""
    
    # 支持的安全算法列表
    SECURE_ALGORITHMS = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]
    
    def __init__(self):
        self.secret_key = settings.JWT_SECRET
        self.algorithm = settings.JWT_ALGORITHM
        self.expire_minutes = settings.JWT_EXPIRE_MINUTES
        self.refresh_expire_minutes = settings.JWT_REFRESH_EXPIRE_MINUTES
        
        # 验证算法是否在安全列表中
        if self.algorithm not in self.SECURE_ALGORITHMS:
            raise ValueError(f"不安全的JWT算法: {self.algorithm}")
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """创建访问令牌"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.expire_minutes)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(self, data: dict) -> str:
        """创建刷新令牌"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.refresh_expire_minutes)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str, token_type: str = "access") -> TokenData:
        """验证令牌"""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # 验证token类型
            if payload.get("type") != token_type:
                raise credentials_exception
                
            sub: Optional[str] = payload.get("sub")
            openid: Optional[str] = payload.get("openid")
            
            if sub is None and openid is None:
                raise credentials_exception
            
            # 将sub转换为整数类型的user_id
            user_id = int(sub) if sub else None
            token_data = TokenData(user_id=user_id, openid=openid)
            return token_data
            
        except JWTError:
            raise credentials_exception
        except (ValueError, TypeError):
            raise credentials_exception
    
# 创建JWT管理器实例
jwt_manager = JWTManager()


def create_user_token(user_id: int, openid: str) -> dict:
    """创建用户令牌对（访问令牌和刷新令牌）"""
    access_token = jwt_manager.create_access_token(
        data={"sub": str(user_id), "openid": openid}
    )
    refresh_token = jwt_manager.create_refresh_token(
        data={"sub": str(user_id), "openid": openid}
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_EXPIRE_MINUTES * 60
    }