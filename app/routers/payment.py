from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import xml.etree.ElementTree as ET
import json

from app.models.database import get_db, User, PaymentOrder
from app.models.schemas import (
    APIResponse, GetOpenidRequest, GetOpenidResponse,
    UnifiedOrderRequest, UnifiedOrderResponse, PaymentCallbackRequest,
    PaymentCallbackResponse, PaymentOrderResponse, PaymentOrderListResponse,
    PaymentOrderFilterParams, PaginationParams
)
from app.services.payment_service import PaymentService
from app.services.user_service import UserService
from app.middleware.auth import get_current_user, get_client_ip


router = APIRouter(prefix="/payment", tags=["微信支付"])


@router.post("/getOpenid", response_model=GetOpenidResponse)
async def get_openid(
    request_data: GetOpenidRequest,
    db: Session = Depends(get_db)
):
    """
    获取微信用户openid
    
    此接口保持与原JS版本兼容，但建议使用云托管优化的登录方式
    """
    try:
        payment_service = PaymentService(db)
        result = await payment_service.get_openid_by_code(request_data.code)
        
        return GetOpenidResponse(**result)
        
    except Exception as e:
        return GetOpenidResponse(
            errcode=-1,
            errmsg=str(e)
        )


@router.post("/unifiedOrder", response_model=APIResponse)
async def unified_order(
    request_data: UnifiedOrderRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    微信支付统一下单接口
    """
    try:
        client_ip = get_client_ip(request)
        payment_service = PaymentService(db)
        
        # 验证openid是否属于当前用户
        if request_data.openid != current_user.openid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="openid不匹配"
            )
        
        result = await payment_service.unified_order(
            request_data, 
            current_user.id, 
            client_ip
        )
        
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
            detail=f"统一下单失败: {str(e)}"
        )


@router.post("/callback", response_model=PaymentCallbackResponse)
async def payment_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    微信支付结果回调接口
    
    此接口由微信支付系统调用，用于通知支付结果
    """
    try:
        # 获取原始请求数据用于调试
        raw_body = await request.body()
        content_type = request.headers.get("content-type", "")
        
        print(f"支付回调 - Content-Type: {content_type}")
        print(f"支付回调 - 原始数据: {raw_body.decode('utf-8') if raw_body else 'Empty body'}")
        
        callback_data = None
        
        # 尝试解析JSON数据
        if "application/json" in content_type.lower():
            try:
                json_data = await request.json()
                print(f"支付回调 - JSON数据: {json_data}")
                
                # 手动创建PaymentCallbackRequest对象，使用实际的驼峰命名字段
                callback_data = PaymentCallbackRequest(
                    return_code=json_data.get("returnCode", ""),
                    result_code=json_data.get("resultCode", ""),
                    out_trade_no=json_data.get("outTradeNo", ""),
                    transaction_id=json_data.get("transactionId"),
                    total_fee=json_data.get("totalFee"),
                    openid=json_data.get("subOpenid"),  # 使用subOpenid字段
                    time_end=json_data.get("timeEnd")
                )
                
            except Exception as parse_error:
                print(f"支付回调 - JSON解析失败: {parse_error}")
        
        # 尝试解析XML数据
        elif "application/xml" in content_type.lower() or "text/xml" in content_type.lower() or raw_body.strip().startswith(b'<'):
            try:
                xml_str = raw_body.decode('utf-8')
                print(f"支付回调 - XML数据: {xml_str}")
                
                root = ET.fromstring(xml_str)
                
                # 解析XML中的字段
                xml_data = {}
                for child in root:
                    xml_data[child.tag] = child.text
                
                print(f"支付回调 - 解析后的XML数据: {xml_data}")
                
                # 创建PaymentCallbackRequest对象，支持两种命名方式
                callback_data = PaymentCallbackRequest(
                    return_code=xml_data.get("return_code") or xml_data.get("returnCode", ""),
                    result_code=xml_data.get("result_code") or xml_data.get("resultCode", ""),
                    out_trade_no=xml_data.get("out_trade_no") or xml_data.get("outTradeNo", ""),
                    transaction_id=xml_data.get("transaction_id") or xml_data.get("transactionId"),
                    total_fee=int(xml_data.get("total_fee") or xml_data.get("totalFee", 0)) if (xml_data.get("total_fee") or xml_data.get("totalFee")) else None,
                    openid=xml_data.get("openid") or xml_data.get("subOpenid"),
                    time_end=xml_data.get("time_end") or xml_data.get("timeEnd")
                )
                
            except Exception as parse_error:
                print(f"支付回调 - XML解析失败: {parse_error}")
        
        # 如果无法解析数据，尝试直接从表单数据中获取
        else:
            try:
                form_data = await request.form()
                print(f"支付回调 - 表单数据: {dict(form_data)}")
                
                callback_data = PaymentCallbackRequest(
                    return_code=form_data.get("return_code") or form_data.get("returnCode", ""),
                    result_code=form_data.get("result_code") or form_data.get("resultCode", ""),
                    out_trade_no=form_data.get("out_trade_no") or form_data.get("outTradeNo", ""),
                    transaction_id=form_data.get("transaction_id") or form_data.get("transactionId"),
                    total_fee=int(form_data.get("total_fee") or form_data.get("totalFee", 0)) if (form_data.get("total_fee") or form_data.get("totalFee")) else None,
                    openid=form_data.get("openid") or form_data.get("subOpenid"),
                    time_end=form_data.get("time_end") or form_data.get("timeEnd")
                )
                
            except Exception as parse_error:
                print(f"支付回调 - 表单解析失败: {parse_error}")
        
        # 如果所有解析都失败，返回成功避免重复回调
        if callback_data is None:
            print("支付回调 - 无法解析任何格式的数据，返回成功状态")
            return PaymentCallbackResponse(
                errcode=0,
                errmsg="OK"
            )
        
        payment_service = PaymentService(db)
        result = payment_service.handle_payment_callback(callback_data)
        
        return PaymentCallbackResponse(**result)
        
    except Exception as e:
        print(f"支付回调处理异常: {str(e)}")
        # 支付回调失败也要返回成功，避免微信重复回调
        return PaymentCallbackResponse(
            errcode=0,
            errmsg="OK"
        )


@router.post("/create-order", response_model=APIResponse)
async def create_payment_order(
    request_data: UnifiedOrderRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    创建支付订单（不调用微信支付，仅创建本地订单）
    """
    try:
        client_ip = get_client_ip(request)
        payment_service = PaymentService(db)
        
        # 如果没有提供out_trade_no，自动生成
        if not request_data.out_trade_no:
            request_data.out_trade_no = payment_service.generate_out_trade_no(current_user.id)
        
        # 创建订单数据
        from app.models.schemas import PaymentOrderCreate
        order_data = PaymentOrderCreate(
            user_id=current_user.id,
            openid=current_user.openid,
            out_trade_no=request_data.out_trade_no,
            body=request_data.body,
            total_fee=request_data.total_fee,
            ip_address=client_ip
        )
        
        order = payment_service.create_payment_order(order_data)
        db.commit()
        
        # 转换为响应模型
        order_response = PaymentOrderResponse.model_validate(order)
        
        return APIResponse(
            code=0,
            message="success",
            data={
                "order": order_response.model_dump()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建订单失败: {str(e)}"
        )


@router.get("/orders/me", response_model=APIResponse)
async def get_my_payment_orders(
    pagination: PaginationParams = Depends(),
    filters: PaymentOrderFilterParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取当前用户的支付订单列表
    """
    try:
        payment_service = PaymentService(db)
        result = payment_service.get_user_payment_orders(
            current_user.id, pagination, filters
        )
        
        # 转换orders为可序列化的格式
        orders_data = []
        for order in result["orders"]:
            order_response = PaymentOrderResponse.model_validate(order)
            orders_data.append(order_response.model_dump())
        
        return APIResponse(
            code=0,
            message="success",
            data={
                "orders": orders_data,
                "total": result["total"],
                "page": result["page"],
                "size": result["size"],
                "pages": result["pages"]
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取订单列表失败: {str(e)}"
        )


@router.get("/orders", response_model=APIResponse)
async def get_all_payment_orders(
    pagination: PaginationParams = Depends(),
    filters: PaymentOrderFilterParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取所有支付订单列表（管理员功能）
    """
    try:
        # 权限检查：仅管理员可访问
        user_service = UserService(db)
        if not user_service.is_admin_user(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied"
            )
        
        payment_service = PaymentService(db)
        result = payment_service.get_all_payment_orders(pagination, filters)
        
        # 转换orders为可序列化的格式
        orders_data = []
        for order in result["orders"]:
            order_response = PaymentOrderResponse.model_validate(order)
            orders_data.append(order_response.model_dump())
        
        return APIResponse(
            code=0,
            message="success",
            data={
                "orders": orders_data,
                "total": result["total"],
                "page": result["page"],
                "size": result["size"],
                "pages": result["pages"]
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取订单列表失败: {str(e)}"
        )


@router.get("/orders/{order_id}", response_model=APIResponse)
async def get_payment_order_by_id(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    根据ID获取支付订单详情
    """
    try:
        payment_service = PaymentService(db)
        order = payment_service.get_payment_order_by_id(order_id)
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="订单不存在"
            )
        
        # 权限检查：用户只能查看自己的订单，管理员可以查看所有
        user_service = UserService(db)
        if (order.user_id != current_user.id and 
            not user_service.is_admin_user(current_user.id)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied"
            )
        
        order_response = PaymentOrderResponse.model_validate(order)
        
        return APIResponse(
            code=0,
            message="success",
            data={
                "order": order_response.model_dump()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取订单详情失败: {str(e)}"
        )


@router.get("/orders/by-trade-no/{out_trade_no}", response_model=APIResponse)
async def get_payment_order_by_trade_no(
    out_trade_no: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    根据商户订单号获取支付订单详情
    """
    try:
        payment_service = PaymentService(db)
        order = payment_service.get_payment_order_by_out_trade_no(out_trade_no)
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="订单不存在"
            )
        
        # 权限检查：用户只能查看自己的订单，管理员可以查看所有
        user_service = UserService(db)
        if (order.user_id != current_user.id and 
            not user_service.is_admin_user(current_user.id)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied"
            )
        
        order_response = PaymentOrderResponse.model_validate(order)
        
        return APIResponse(
            code=0,
            message="success",
            data={
                "order": order_response.model_dump()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取订单详情失败: {str(e)}"
        )


@router.get("/health", response_model=APIResponse)
async def payment_health_check():
    """支付模块健康检查"""
    return APIResponse(
        code=0,
        message="success",
        data={
            "status": "healthy",
            "module": "payment"
        }
    )