import httpx
import json
import hashlib
import secrets
import string
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import HTTPException, status

from app.config import settings
from app.models.database import PaymentOrder, User, BookingStatusEnum
from app.models.schemas import (
    UnifiedOrderRequest, PaymentCallbackRequest, PaymentOrderCreate,
    PaymentStatusEnum, PaymentOrderResponse, PaymentOrderListResponse,
    PaymentOrderFilterParams, PaginationParams
)
from app.services.wechat_service import WechatService


class PaymentService:
    """支付服务类，处理微信支付相关功能"""
    
    def __init__(self, db: Session):
        self.db = db
        self.wechat_service = WechatService()
        self.app_id = settings.WECHAT_APP_ID
        self.app_secret = settings.WECHAT_APP_SECRET
        self.mch_id = settings.WECHAT_MCH_ID
        self.mch_key = settings.WECHAT_MCH_KEY
        self.sub_mch_id = settings.WECHAT_SUB_MCH_ID
        self.cloud_env_id = settings.CLOUD_ENV_ID
        self.disable_ssl_validation = settings.DISABLE_WECHAT_SSL_VALIDATION
    
    async def get_openid_by_code(self, code: str) -> Dict[str, Any]:
        """
        通过微信登录code获取openid
        
        Args:
            code: 微信登录code
            
        Returns:
            Dict包含errcode和openid
        """
        try:
            # 使用已有的微信服务获取openid
            wechat_data = await self.wechat_service.get_openid_by_code(code)
            
            return {
                "errcode": 0,
                "openid": wechat_data["openid"]
            }
            
        except HTTPException as e:
            # 转换为支付模块的错误格式
            return {
                "errcode": -1,
                "errmsg": str(e.detail)
            }
        except Exception as e:
            return {
                "errcode": -1,
                "errmsg": f"获取openid失败: {str(e)}"
            }
    
    def generate_out_trade_no(self, user_id: int) -> str:
        """
        生成商户订单号
        
        Args:
            user_id: 用户ID
            
        Returns:
            商户订单号
        """
        # 生成格式: 时间戳 + 用户ID + 随机数
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_str = ''.join(secrets.choice(string.digits) for _ in range(6))
        return f"{timestamp}{user_id:06d}{random_str}"
    
    def create_payment_order(self, order_data: PaymentOrderCreate, allow_duplicate: bool = False) -> PaymentOrder:
        """
        创建支付订单
        
        Args:
            order_data: 订单数据
            allow_duplicate: 是否允许重复订单号，默认False
            
        Returns:
            创建的订单对象
        """
        # 检查订单号是否已存在
        print(f"[DEBUG] 检查订单号是否存在: {order_data.out_trade_no}")
        existing_order = self.db.query(PaymentOrder).filter(
            PaymentOrder.out_trade_no == order_data.out_trade_no
        ).first()

        if existing_order:
            print(f"[DEBUG] 找到已存在订单: ID {existing_order.id}, 订单号 {existing_order.out_trade_no}")
            if not allow_duplicate:
                # 如果不允许重复，返回已存在的订单而不是抛出异常
                print(f"[DEBUG] 不允许重复，返回已存在订单: {existing_order.id}, 商户订单号: {existing_order.out_trade_no}")
                return existing_order
            else:
                # 如果允许重复但订单已存在，直接返回已存在的订单
                print(f"[DEBUG] 允许重复但订单已存在，返回已存在订单: {existing_order.id}, 商户订单号: {existing_order.out_trade_no}")
                return existing_order
        else:
            print(f"[DEBUG] 订单号不存在，将创建新订单: {order_data.out_trade_no}")
        
        # 创建新订单
        order = PaymentOrder(**order_data.dict())
        self.db.add(order)
        self.db.flush()  # 获取order.id
        
        print(f"创建新的支付订单: {order.id}, 商户订单号: {order.out_trade_no}")
        return order
    
    async def unified_order(
        self,
        request_data: UnifiedOrderRequest,
        user_id: int,
        ip_address: str
    ) -> Dict[str, Any]:
        """
        微信支付统一下单
        
        Args:
            request_data: 下单请求数据
            user_id: 用户ID
            ip_address: 客户端IP
            
        Returns:
            Dict包含支付参数或错误信息
        """
        try:
            # 确保商户订单号格式一致
            out_trade_no = request_data.out_trade_no
            print(f"[DEBUG] 支付时接收到的原始订单号: {out_trade_no}")
            if not out_trade_no:
                # 如果没有提供商户订单号，生成一个
                out_trade_no = self.generate_out_trade_no(user_id)
                print(f"[DEBUG] 支付时未提供订单号，生成新订单号: {out_trade_no}")
            elif out_trade_no.startswith('BOOKING'):
                # 如果是预订相关的订单，直接使用原始订单号
                print(f"[DEBUG] 支付时使用预订相关订单号: {out_trade_no}")
                pass
            else:
                # 如果不是预订相关的订单，检查格式是否一致
                # 如果格式不一致，生成一个新的统一格式的订单号
                # 这样可以确保订单号格式一致，避免重复创建订单
                if len(out_trade_no) != 26 or not out_trade_no.isdigit():
                    print(f"[DEBUG] 支付时订单号格式不一致，重新生成: {out_trade_no} -> {self.generate_out_trade_no(user_id)}")
                    out_trade_no = self.generate_out_trade_no(user_id)
            
            # 使用create_payment_order方法创建或获取订单（确保幂等性）
            order_data = PaymentOrderCreate(
                user_id=user_id,
                openid=request_data.openid,
                out_trade_no=out_trade_no,
                body=request_data.body,
                total_fee=request_data.total_fee,
                status=PaymentStatusEnum.PENDING,
                transaction_id=None,
                ip_address=ip_address
            )
            
            # 允许重复，但实际上会返回已存在的订单
            order = self.create_payment_order(order_data, allow_duplicate=True)
            
            # 查找并关联对应的预订（无论订单号是否以BOOKING开头）
            # 只在订单还没有关联预订时才进行关联
            from app.models.database import Booking
            # 检查是否已经有预订关联到这个订单
            existing_booking = self.db.query(Booking).filter(
                Booking.payment_order_id == order.id
            ).first()
            
            # 尝试关联对应的预订，优先使用提供的booking_id
            # 允许更新已有关联的支付订单，特别是对于待支付状态的预订
            from app.models.database import BookingStatusEnum
            
            # 优先使用请求中提供的booking_id
            if hasattr(request_data, 'booking_id') and request_data.booking_id:
                booking = self.db.query(Booking).filter(
                    and_(
                        Booking.id == request_data.booking_id,
                        Booking.user_id == user_id,
                        Booking.status == BookingStatusEnum.PENDING  # 只关联待支付的预订
                    )
                ).first()
                
                if booking:
                    # 无论是否已有关联支付订单，都更新为新的支付订单ID
                    booking.payment_order_id = order.id
                    print(f"通过booking_id更新预订支付关联: 预订ID {booking.id} -> 支付订单ID {order.id}")
                else:
                    print(f"提供的booking_id {request_data.booking_id} 未找到或不是待支付状态")
            else:
                # 如果没有提供booking_id，查找用户最新的待支付预订
                booking = self.db.query(Booking).filter(
                    and_(
                        Booking.user_id == user_id,
                        Booking.status == BookingStatusEnum.PENDING  # 只关联待支付的预订
                    )
                ).order_by(Booking.created_at.desc()).first()
                
                if booking:
                    booking.payment_order_id = order.id
                    print(f"自动关联待支付预订: 预订ID {booking.id} -> 支付订单ID {order.id}")
            
            # 确保订单的openid是最新的
            if order.openid != request_data.openid:
                order.openid = request_data.openid
                print(f"更新支付订单openid: {order.id}")
            
            print(f"处理支付订单: {order.id}, 商户订单号: {order.out_trade_no}")
            
            # 调用微信支付统一下单接口
            pay_url = "http://api.weixin.qq.com/_/pay/unifiedOrder"
            
            pay_data = {
                "openid": request_data.openid,
                "body": request_data.body,
                "out_trade_no": out_trade_no,  # 使用处理后的订单号，确保一致性
                "total_fee": request_data.total_fee,
                "spbill_create_ip": ip_address,
                "sub_mch_id": self.mch_id,
                "env_id": self.cloud_env_id,
                "callback_type": 2,
                "container": {
                    "service": "xinghui",  # 服务名称，需要匹配云托管控制台
                    "path": "/api/v1/payment/callback"
                }
            }
            
            # 配置HTTP客户端
            verify_ssl = not self.disable_ssl_validation
            timeout = httpx.Timeout(10.0)
            
            async with httpx.AsyncClient(verify=verify_ssl, timeout=timeout) as client:
                response = await client.post(
                    pay_url,
                    json=pay_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"微信支付接口请求失败: {response.status_code}"
                    )
                
                result = response.json()
                
                if result.get("errcode", -1) != 0:
                    # 更新订单状态为失败
                    order.status = PaymentStatusEnum.FAILED
                    self.db.commit()
                    
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=result.get("errmsg", "微信支付下单失败")
                    )
                
                # 更新订单的prepay_id
                if "respdata" in result and "payment" in result["respdata"]:
                    payment_info = result["respdata"]["payment"]
                    if "package" in payment_info:
                        # 从package中提取prepay_id
                        package = payment_info["package"]
                        if package.startswith("prepay_id="):
                            order.prepay_id = package[10:]  # 去掉"prepay_id="前缀
                
                self.db.commit()
                
                return {
                    "errcode": 0,
                    "payment": result["respdata"]["payment"]
                }
                
        except HTTPException:
            # 回滚事务
            self.db.rollback()
            raise
        except Exception as e:
            # 回滚事务
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"统一下单失败: {str(e)}"
            )
    
    def handle_payment_callback(self, callback_data: PaymentCallbackRequest) -> Dict[str, Any]:
        """
        处理支付结果回调
        
        Args:
            callback_data: 回调数据
            
        Returns:
            Dict包含处理结果
        """
        try:
            # 查找订单
            order = self.db.query(PaymentOrder).filter(
                PaymentOrder.out_trade_no == callback_data.out_trade_no
            ).first()
            
            if not order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="订单不存在"
                )
            
            # 更新订单状态
            if (callback_data.return_code == "SUCCESS" and 
                callback_data.result_code == "SUCCESS"):
                
                order.status = PaymentStatusEnum.SUCCESS
                order.transaction_id = callback_data.transaction_id
                order.paid_at = datetime.utcnow()
                
                # 更新关联的预订状态
                from app.models.database import Booking
                from app.models.schemas import BookingStatusEnum
                
                booking = self.db.query(Booking).filter(
                    Booking.payment_order_id == order.id
                ).first()
                
                if booking:
                    booking.status = BookingStatusEnum.CONFIRMED
                    booking.updated_at = datetime.utcnow()
                    print(f"更新预订状态: 预订ID {booking.id} -> confirmed")
                
                print(f"支付成功: 订单号 {callback_data.out_trade_no}, "
                      f"交易号 {callback_data.transaction_id}, "
                      f"金额 {callback_data.total_fee}")
                
            else:
                order.status = PaymentStatusEnum.FAILED
                print(f"支付失败: 订单号 {callback_data.out_trade_no}")
            
            order.updated_at = datetime.utcnow()
            self.db.commit()
            
            return {"errcode": 0, "errmsg": "OK"}
            
        except Exception as e:
            self.db.rollback()
            print(f"支付回调处理失败: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"支付回调处理失败: {str(e)}"
            )
    
    def get_payment_order_by_id(self, order_id: int) -> Optional[PaymentOrder]:
        """根据ID获取支付订单"""
        return self.db.query(PaymentOrder).filter(
            PaymentOrder.id == order_id
        ).first()
    
    def get_payment_order_by_out_trade_no(self, out_trade_no: str) -> Optional[PaymentOrder]:
        """根据商户订单号获取支付订单"""
        return self.db.query(PaymentOrder).filter(
            PaymentOrder.out_trade_no == out_trade_no
        ).first()
    
    def get_user_payment_orders(
        self,
        user_id: int,
        pagination: PaginationParams,
        filters: PaymentOrderFilterParams
    ) -> Dict[str, Any]:
        """
        获取用户的支付订单列表
        
        Args:
            user_id: 用户ID
            pagination: 分页参数
            filters: 过滤参数
            
        Returns:
            订单列表数据
        """
        query = self.db.query(PaymentOrder).filter(
            PaymentOrder.user_id == user_id
        )
        
        # 应用过滤条件
        if filters.status:
            query = query.filter(PaymentOrder.status == filters.status.value)
        if filters.out_trade_no:
            query = query.filter(PaymentOrder.out_trade_no == filters.out_trade_no)
        if filters.transaction_id:
            query = query.filter(PaymentOrder.transaction_id == filters.transaction_id)
        if filters.start_date:
            query = query.filter(PaymentOrder.created_at >= filters.start_date)
        if filters.end_date:
            query = query.filter(PaymentOrder.created_at <= filters.end_date)
        
        # 获取总数
        total = query.count()
        
        # 分页查询
        orders = query.order_by(PaymentOrder.created_at.desc()).offset(
            (pagination.page - 1) * pagination.size
        ).limit(pagination.size).all()
        
        # 计算总页数
        pages = (total + pagination.size - 1) // pagination.size
        
        return {
            "orders": orders,
            "total": total,
            "page": pagination.page,
            "size": pagination.size,
            "pages": pages
        }
    
    def get_all_payment_orders(
        self,
        pagination: PaginationParams,
        filters: PaymentOrderFilterParams
    ) -> Dict[str, Any]:
        """
        获取所有支付订单列表（管理员功能）
        
        Args:
            pagination: 分页参数
            filters: 过滤参数
            
        Returns:
            订单列表数据
        """
        query = self.db.query(PaymentOrder)
        
        # 应用过滤条件
        if filters.status:
            query = query.filter(PaymentOrder.status == filters.status.value)
        if filters.out_trade_no:
            query = query.filter(PaymentOrder.out_trade_no == filters.out_trade_no)
        if filters.transaction_id:
            query = query.filter(PaymentOrder.transaction_id == filters.transaction_id)
        if filters.start_date:
            query = query.filter(PaymentOrder.created_at >= filters.start_date)
        if filters.end_date:
            query = query.filter(PaymentOrder.created_at <= filters.end_date)
        
        # 获取总数
        total = query.count()
        
        # 分页查询
        orders = query.order_by(PaymentOrder.created_at.desc()).offset(
            (pagination.page - 1) * pagination.size
        ).limit(pagination.size).all()
        
        # 计算总页数
        pages = (total + pagination.size - 1) // pagination.size
        
        return {
            "orders": orders,
            "total": total,
            "page": pagination.page,
            "size": pagination.size,
            "pages": pages
        }