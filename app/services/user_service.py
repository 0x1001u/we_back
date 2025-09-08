from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from fastapi import HTTPException, status
from app.models.database import User, AuditLog, UserSession, get_db
from app.models.schemas import (
    UserCreate, UserUpdate, UserResponse, WechatUserInfo,
    PaginationParams, UserFilterParams, AuditLogFilterParams, AuditLogCreate
)
from app.utils.jwt import jwt_manager, create_user_token
import hashlib
import secrets
import string


class UserService:
    """用户服务类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """根据ID获取用户"""
        return self.db.query(User).filter(
            and_(User.id == user_id, User.is_deleted == False)
        ).first()
    
    def get_user_by_openid(self, openid: str) -> Optional[User]:
        """根据openid获取用户"""
        return self.db.query(User).filter(
            and_(User.openid == openid, User.is_deleted == False)
        ).first()
        
    def is_admin_user(self, user_id: int) -> bool:
        """检查用户是否为管理员"""
        user = self.get_user_by_id(user_id)
        # 目前暂时返回True，即所有用户都是管理员
        # 在实际项目中应该根据用户角色或权限表进行判断
        return user is not None
    
    def create_user(self, user_data: UserCreate, ip_address: str) -> User:
        """创建用户"""
        # 检查用户是否已存在
        existing_user = self.get_user_by_openid(user_data.openid)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists"
            )
        
        # 创建用户
        user = User(**user_data.dict())
        self.db.add(user)
        self.db.flush()  # 获取user.id但不提交事务
        
        # 记录审计日志
        self.create_audit_log(
            user_id=user.id,
            action="CREATE_USER",
            resource_type="USER",
            resource_id=str(user.id),
            old_value=None,
            new_value=user_data.dict(),
            ip_address=ip_address,
            description=f"创建用户: {user.openid}"
        )
        
        return user
    
    def update_user(self, user_id: int, user_data: UserUpdate, ip_address: str) -> User:
        """更新用户信息"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # 获取旧值用于审计日志
        old_values = {
            "nickname": user.nickname,
            "phone": user.phone,
            "email": user.email,
            "gender": user.gender,
            "country": user.country,
            "province": user.province,
            "city": user.city,
            "language": user.language,
            "avatar_url": user.avatar_url
        }
        
        # 定义允许更新的字段白名单
        allowed_fields = {
            "nickname", "phone", "email", "gender",
            "country", "province", "city", "language", "avatar_url"
        }
        
        # 更新用户信息（只允许更新白名单字段）
        update_data = user_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            if field in allowed_fields:
                setattr(user, field, value)
        
        # 掩码敏感数据
        def mask_pii(data):
            if isinstance(data, dict):
                for key in ['phone', 'email']:
                    if key in data and data[key]:
                        data[key] = data[key][:3] + '****' + data[key][-4:]
                return data
            return data
        
        # 记录审计日志
        self.create_audit_log(
            user_id=user.id,
            action="UPDATE_USER",
            resource_type="USER",
            resource_id=str(user.id),
            old_value=mask_pii(old_values),
            new_value=mask_pii(update_data),
            ip_address=ip_address,
            description=f"更新用户信息: {user.openid}"
        )
        
        return user
    
    def delete_user(self, user_id: int, ip_address: str) -> bool:
        """软删除用户"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # 删除用户所有会话
        self.db.query(UserSession).filter(
            UserSession.user_id == user_id
        ).delete()
        
        # 软删除用户
        user.is_deleted = True
        user.updated_at = datetime.utcnow()
        
        # 记录审计日志
        self.create_audit_log(
            user_id=user.id,
            action="DELETE_USER",
            resource_type="USER",
            resource_id=str(user.id),
            old_value={"is_deleted": False},
            new_value={"is_deleted": True},
            ip_address=ip_address,
            description=f"删除用户: {user.openid}"
        )
        
        return True
    
    def get_users_list(
        self,
        pagination: PaginationParams,
        filters: UserFilterParams
    ) -> Dict[str, Any]:
        """获取用户列表（分页）"""
        query = self.db.query(User).filter(User.is_deleted == False)
        
        # 应用过滤条件
        if filters.nickname:
            query = query.filter(User.nickname.contains(filters.nickname))
        if filters.phone:
            query = query.filter(User.phone == filters.phone)
        if filters.email:
            query = query.filter(User.email == filters.email)
        if filters.is_active is not None:
            query = query.filter(User.is_active == filters.is_active)
        if filters.start_date:
            query = query.filter(User.created_at >= filters.start_date)
        if filters.end_date:
            query = query.filter(User.created_at <= filters.end_date)
        
        # 获取总数
        total = query.count()
        
        # 分页查询
        users = query.order_by(User.created_at.desc()).offset(
            (pagination.page - 1) * pagination.size
        ).limit(pagination.size).all()
        
        # 计算总页数
        pages = (total + pagination.size - 1) // pagination.size
        
        return {
            "users": users,
            "total": total,
            "page": pagination.page,
            "size": pagination.size,
            "pages": pages
        }
        
    def get_audit_logs(
        self,
        user_id: int,
        pagination: PaginationParams,
        filters: AuditLogFilterParams
    ) -> Dict[str, Any]:
        """获取用户审计日志"""
        from app.models.database import AuditLog
        
        query = self.db.query(AuditLog).filter(AuditLog.user_id == user_id)
        
        # 应用过滤条件
        if filters.action:
            query = query.filter(AuditLog.action == filters.action)
        if filters.resource_type:
            query = query.filter(AuditLog.resource_type == filters.resource_type)
        if filters.start_date:
            query = query.filter(AuditLog.created_at >= filters.start_date)
        if filters.end_date:
            query = query.filter(AuditLog.created_at <= filters.end_date)
        
        # 获取总数
        total = query.count()
        
        # 分页查询
        logs = query.order_by(AuditLog.created_at.desc()).offset(
            (pagination.page - 1) * pagination.size
        ).limit(pagination.size).all()
        
        # 计算总页数
        pages = (total + pagination.size - 1) // pagination.size
        
        return {
            "logs": logs,
            "total": total,
            "page": pagination.page,
            "size": pagination.size,
            "pages": pages
        }
        
    def validate_token_ownership(self, user_id: int, token: str) -> bool:
        """验证token所有权"""
        session = self.db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.token == token,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.utcnow()
            )
        ).first()
        
        return session is not None
    
    def _generate_csrf_token(self) -> str:
        """生成CSRF令牌"""
        # 生成一个32字符的随机字符串作为CSRF令牌
        alphabet = string.ascii_letters + string.digits
        csrf_token = ''.join(secrets.choice(alphabet) for _ in range(32))
        return csrf_token
    
    def auto_register_or_login(self, wechat_info: WechatUserInfo, ip_address: str) -> Dict[str, Any]:
        """自动注册或登录用户"""
        try:
            # 开启事务
            with self.db.begin_nested():
                # 基本验证微信信息
                if not all([
                    wechat_info.openid,
                    wechat_info.nickname,
                    wechat_info.avatar_url
                ]):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid WeChat user info"
                    )
                
                # 查找用户
                user = self.get_user_by_openid(wechat_info.openid)
                
                if not user:
                    # 创建新用户
                    user_data = UserCreate(
                        openid=wechat_info.openid,
                        unionid=wechat_info.unionid,
                        nickname=wechat_info.nickname,
                        avatar_url=wechat_info.avatar_url,
                        gender=wechat_info.gender,
                        country=wechat_info.country,
                        province=wechat_info.province,
                        city=wechat_info.city,
                        language=wechat_info.language,
                        phone=None,
                        email=None
                    )
                    user = self.create_user(user_data, ip_address)
                    action = "AUTO_REGISTER"
                else:
                    # 更新用户信息
                    user_data = UserUpdate(
                        nickname=wechat_info.nickname,
                        avatar_url=wechat_info.avatar_url,
                        gender=wechat_info.gender,
                        country=wechat_info.country,
                        province=wechat_info.province,
                        city=wechat_info.city,
                        language=wechat_info.language,
                        phone=None,
                        email=None
                    )
                    user = self.update_user(user.id, user_data, ip_address)
                    action = "AUTO_LOGIN"
                
                # 创建JWT令牌
                token_data = create_user_token(user.id, user.openid)
                
                # 生成CSRF令牌
                csrf_token = self._generate_csrf_token()
                
                # 记录用户会话
                self.create_user_session(
                    user_id=user.id,
                    token=token_data["access_token"],
                    refresh_token=token_data["refresh_token"],
                    ip_address=ip_address
                )
                
                # 记录审计日志
                self.create_audit_log(
                    user_id=user.id,
                    action=action,
                    resource_type="USER",
                    resource_id=str(user.id),
                    ip_address=ip_address,
                    description=f"{action}: {user.openid}"
                )
            
            # 提交外层事务
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Auto register/login failed: {str(e)}"
            )
        
        return {
            "user": user,
            "token": token_data,
            "action": action,
            "csrf_token": csrf_token
        }
    
    def create_audit_log(
        self,
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: str,
        old_value: Any = None,
        new_value: Any = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        description: Optional[str] = None,
        commit: bool = False
    ) -> AuditLog:
        """创建审计日志"""
        # 使用JSON序列化复杂对象
        import json
        try:
            old_value_str = json.dumps(old_value, ensure_ascii=False) if old_value else None
        except TypeError:
            old_value_str = str(old_value)
        
        try:
            new_value_str = json.dumps(new_value, ensure_ascii=False) if new_value else None
        except TypeError:
            new_value_str = str(new_value)
        
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=old_value_str,
            new_value=new_value_str,
            ip_address=ip_address,
            user_agent=user_agent,
            description=description
        )
        self.db.add(audit_log)
        
        if commit:
            self.db.commit()
            self.db.refresh(audit_log)
        
        return audit_log
    
    def create_user_session(
        self,
        user_id: int,
        token: str,
        refresh_token: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        commit: bool = False
    ) -> UserSession:
        """创建用户会话"""
        # 计算过期时间
        expires_at = datetime.utcnow() + timedelta(minutes=jwt_manager.expire_minutes)
        refresh_expires_at = None
        if refresh_token:
            refresh_expires_at = datetime.utcnow() + timedelta(minutes=jwt_manager.refresh_expire_minutes)
        
        # 清理该用户的过期会话
        self.db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.expires_at < datetime.utcnow()
            )
        ).delete()
        
        # 创建新会话
        session = UserSession(
            user_id=user_id,
            token=token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            refresh_expires_at=refresh_expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )
        self.db.add(session)
        
        if commit:
            self.db.commit()
            self.db.refresh(session)
        
        return session
    
    def validate_user_session(self, user_id: int, token: str) -> bool:
        """验证用户会话"""
        from app.utils.jwt import jwt_manager
        
        # 先验证JWT有效性
        try:
            token_data = jwt_manager.verify_token(token, "access")
            if token_data.user_id != user_id:
                return False
        except Exception:
            return False
        
        # 再验证会话是否存在
        session = self.db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.token == token,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.utcnow()
            )
        ).first()
        
        return session is not None
    
    def logout_user(self, user_id: int, token: str, ip_address: str) -> bool:
        """用户登出"""
        session = self.db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.token == token,
                UserSession.is_active == True
            )
        ).first()
        
        if session:
            session.is_active = False
            session.refresh_token = None  # 清除refresh token
            session.refresh_expires_at = None
            self.db.commit()
            
            # 记录审计日志
            self.create_audit_log(
                user_id=user_id,
                action="LOGOUT",
                resource_type="USER_SESSION",
                resource_id=str(session.id),
                ip_address=ip_address,
                description=f"用户登出: {user_id}"
            )
            
            return True
        
        return False