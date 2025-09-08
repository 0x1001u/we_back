from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, Form, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.database import get_db, User
from app.models.schemas import (
    UserResponse, UserUpdate, WechatUserInfo, Token, WechatLoginRequest,
    PaginationParams, UserFilterParams, UserListResponse,
    APIResponse, UploadResponse, AuditLogListResponse,
    AuditLogFilterParams, GenderEnum
)
from app.services.user_service import UserService
from app.services.wechat_service import WechatService
from app.utils.file_upload import file_upload_service
from app.middleware.auth import get_current_user, get_wechat_headers, get_client_ip, get_user_agent
from app.models.database import create_tables

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.on_event("startup")
async def startup_event():
    """应用启动时创建数据库表"""
    create_tables()


@router.post("/auto-login", response_model=APIResponse)
async def auto_login(
    request: Request,
    login_request: WechatLoginRequest,
    db: Session = Depends(get_db)
):
    """自动注册或登录用户"""
    try:
        # DEBUG: Log incoming login request
        print(f"[DEBUG] Received login request: code={login_request.code}, user_info={login_request.user_info}")
        
        client_ip = get_client_ip(request)
        user_agent = get_user_agent(request)
        
        # 创建微信服务实例
        wechat_service = WechatService()
        
        # 通过code获取openid
        wechat_auth_data = await wechat_service.get_openid_by_code(login_request.code)
        
        # DEBUG: Log wechat auth data
        print(f"[DEBUG] Wechat auth data: {wechat_auth_data}")
        
        # 将openid与用户信息结合
        wechat_info = WechatUserInfo(
            openid=wechat_auth_data["openid"],
            unionid=wechat_auth_data.get("unionid") or login_request.user_info.unionid,
            nickName=login_request.user_info.nickname,  # 使用别名nickName
            avatarUrl=login_request.user_info.avatar_url,  # 使用别名avatarUrl
            gender=login_request.user_info.gender,
            country=login_request.user_info.country,
            province=login_request.user_info.province,
            city=login_request.user_info.city,
            language=login_request.user_info.language
        )
        
        # 调用用户服务进行登录或注册
        user_service = UserService(db)
        result = user_service.auto_register_or_login(wechat_info, client_ip)
        
        # DEBUG: Log login result
        print(f"[DEBUG] Login result: action={result['action']}, user_id={result['user'].id}")
        
        # 使用Pydantic模型转换用户对象为可序列化字典
        user_dict = UserResponse.model_validate(result["user"]).model_dump()
        
        # 转换token对象中的datetime字段为字符串
        token_data = result["token"]  # 直接使用字典对象
        if "expires_at" in token_data and token_data["expires_at"] is not None:
            token_data["expires_at"] = token_data["expires_at"].isoformat()
        
        response_data = {
            "code": 0,
            "message": "success",
            "data": {
                "user": user_dict,
                "token": token_data,  # 使用转换后的token数据
                "action": result["action"]
            }
        }
        response = JSONResponse(content=response_data)
        
        # 设置CSRF令牌Cookie
        response.set_cookie(
            key="csrftoken",
            value=result["csrf_token"],
            httponly=False,
            samesite="strict",
            secure=True
        )
        
        return response
        
    except Exception as e:
        # DEBUG: Log full exception
        print(f"[ERROR] Login failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/me", response_model=APIResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """获取当前用户信息"""
    try:
        # 使用Pydantic模型转换用户对象为可序列化字典
        user_dict = UserResponse.model_validate(current_user).model_dump()
        return APIResponse(
            code=0,
            message="success",
            data={
                "user": user_dict
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/me", response_model=APIResponse)
async def update_current_user(
    user_update: UserUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新当前用户信息"""
    try:
        client_ip = get_client_ip(request)
        user_service = UserService(db)
        
        updated_user = user_service.update_user(current_user.id, user_update, client_ip)
        
        # 使用Pydantic模型转换用户对象为可序列化字典
        user_dict = UserResponse.model_validate(updated_user).model_dump()
        return APIResponse(
            code=0,
            message="success",
            data={
                "user": user_dict
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/me/avatar", response_model=APIResponse)
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传用户头像"""
    try:
        client_ip = get_client_ip(request)
        user_service = UserService(db)
        
        # 上传头像
        upload_result = await file_upload_service.upload_avatar(file, current_user.id)
        
        # 删除旧头像
        if current_user.avatar_url:
            await file_upload_service.delete_file(current_user.avatar_url)
        
        # 更新用户头像（只更新avatar_url字段）
        user_update = UserUpdate(
            avatar_url=upload_result["file_url"],
            nickname=current_user.nickname,  # 保留原值
            phone=current_user.phone,
            email=current_user.email,
            country=current_user.country,
            province=current_user.province,
            city=current_user.city,
            language=current_user.language
        )
        # 单独处理gender字段（转换为枚举类型）
        if current_user.gender is not None:
            user_update.gender = GenderEnum(current_user.gender)
        updated_user = user_service.update_user(current_user.id, user_update, client_ip)
        
        # 使用Pydantic模型转换用户对象为可序列化字典
        user_dict = UserResponse.model_validate(updated_user).model_dump()
        return APIResponse(
            code=0,
            message="success",
            data={
                "user": user_dict,
                "avatar": upload_result
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/", response_model=APIResponse)
async def get_users_list(
    pagination: PaginationParams = Depends(),
    filters: UserFilterParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户列表（分页）"""
    try:
        # 权限检查：仅管理员可访问用户列表
        user_service = UserService(db)
        if not user_service.is_admin_user(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied"
            )
            
        result = user_service.get_users_list(pagination, filters)
        
        return APIResponse(
            code=0,
            message="success",
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{user_id}", response_model=APIResponse)
async def get_user_by_id(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """根据ID获取用户"""
    try:
        user_service = UserService(db)
        user = user_service.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # 使用Pydantic模型转换用户对象为可序列化字典
        user_dict = UserResponse.model_validate(user).model_dump()
        return APIResponse(
            code=0,
            message="success",
            data={
                "user": user_dict
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除用户（软删除）"""
    try:
        client_ip = get_client_ip(request)
        user_service = UserService(db)
        
        # 检查权限：管理员才能删除用户
        if not user_service.is_admin_user(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied"
            )
        
        # 不能删除自己
        if user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete yourself"
            )
        
        success = user_service.delete_user(user_id, client_ip)
        
        # 204响应不需要返回内容
        from fastapi import Response
        return Response(status_code=status.HTTP_204_NO_CONTENT)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{user_id}/audit-logs", response_model=APIResponse)
async def get_user_audit_logs(
    user_id: int,
    pagination: PaginationParams = Depends(),
    filters: AuditLogFilterParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户审计日志"""
    try:
        user_service = UserService(db)
        
        # 验证用户是否存在
        user = user_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # 权限检查：用户只能查看自己的日志，管理员可以查看所有
        if user_id != current_user.id and not user_service.is_admin_user(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied"
            )
        
        # 获取审计日志（使用服务层方法）
        logs_data = user_service.get_audit_logs(user_id, pagination, filters)
        
        return APIResponse(
            code=0,
            message="success",
            data=logs_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/logout", response_model=APIResponse)
async def logout_user(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """用户登出"""
    try:
        client_ip = get_client_ip(request)
        user_service = UserService(db)
        
        # 获取Authorization头
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid authorization header"
            )
        
        token = auth_header.split(" ")[1]
        
        # 验证token所有权
        if not user_service.validate_token_ownership(current_user.id, token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid token ownership"
            )
        
        # 登出用户
        success = user_service.logout_user(current_user.id, token, client_ip)
        
        return APIResponse(
            code=0,
            message="success",
            data={
                "logged_out": success
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/health", response_model=APIResponse)
async def health_check():
    """健康检查"""
    return APIResponse(
        code=0,
        message="success",
        data={
            "status": "healthy",
            "service": "wechat-miniprogram-backend"
        }
    )