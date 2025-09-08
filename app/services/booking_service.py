import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from fastapi import HTTPException, status

from app.models.database import (
    Booking, Room, User, BookingTimeSlot, BookingStatusEnum, RoomStatusEnum
)
from app.models.schemas import BookingCreate, BookingUpdate, BookingResponse, PaymentStatusEnum
from app.services.payment_service import PaymentService
from app.utils.time_utils import get_time_range

logger = logging.getLogger(__name__)

class BookingService:
    def __init__(self, db: Session):
        self.db = db
        self.payment_service = PaymentService(db)
    
    def check_availability(self, room_id: int, start_time: datetime, end_time: datetime) -> bool:
        """检查房间在指定时间段是否可用"""
        conflicting_bookings = self.db.query(Booking).filter(
            and_(
                Booking.room_id == room_id,
                Booking.status.in_([BookingStatusEnum.CONFIRMED, BookingStatusEnum.PENDING]),
                or_(
                    and_(Booking.start_time < end_time, Booking.end_time > start_time),
                    and_(Booking.start_time >= start_time, Booking.start_time < end_time),
                    and_(Booking.end_time > start_time, Booking.end_time <= end_time)
                )
            )
        ).count()
        
        return conflicting_bookings == 0
    
    def create_booking(self, booking_data: BookingCreate, user_id: int) -> Dict[str, Any]:
        """
        创建预订
        """
        try:
            # 添加调试日志
            print(f"[DEBUG] create_booking - booking_data type: {type(booking_data)}")
            print(f"[DEBUG] create_booking - booking_data: {booking_data}")
            
            # 获取房间信息
            room = self.db.query(Room).filter(Room.id == booking_data.room_id).first()
            if not room:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="房间不存在"
                )
            
            # 检查房间状态
            if not room.is_available:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="房间不可用"
                )
            
            # 检查时间段是否冲突 - 使用datetime对象
            start_time_dt = datetime.fromtimestamp(booking_data.start_time)
            end_time_dt = datetime.fromtimestamp(booking_data.end_time)
            
            if not self.check_availability(booking_data.room_id, start_time_dt, end_time_dt):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="所选时间段已被预订"
                )
            
            # 计算价格
            duration_hours = (end_time_dt - start_time_dt).total_seconds() / 3600
            # 计算原始价格
            original_amount = room.price * duration_hours
            # 应用折扣
            discount = room.discount if room.discount else 1.0
            final_amount = original_amount * discount
            discount_amount = original_amount - final_amount
            
            # 创建预订记录 - 使用整数时间戳，而不是datetime对象
            booking = Booking(
                user_id=user_id,
                room_id=booking_data.room_id,
                booking_date=booking_data.booking_date,
                start_time=booking_data.start_time,  # 使用原始整数时间戳
                end_time=booking_data.end_time,      # 使用原始整数时间戳
                duration=int(duration_hours),  # 确保为整数
                contact_name=booking_data.contact_name,  # 添加联系人姓名
                contact_phone=booking_data.contact_phone,  # 添加联系电话
                remark=booking_data.remark if hasattr(booking_data, 'remark') else None,  # 添加备注
                original_amount=original_amount,
                discount_amount=discount_amount,
                final_amount=final_amount,
                status=BookingStatusEnum.PENDING.value  # 确保状态值正确设置
            )
            
            self.db.add(booking)
            self.db.flush()  # 获取booking.id
            
            # 检查BookingTimeSlot表是否存在，如果存在则创建详细的时间段记录
            from sqlalchemy import inspect
            inspector = inspect(self.db.bind)
            if inspector and inspector.has_table('booking_time_slots'):
                self._create_booking_time_slots(booking, booking_data)
            else:
                print("警告: BookingTimeSlot表不存在，跳过时间段记录创建")
            
            # 生成商户订单号供后续支付使用，确保符合微信支付订单号规范（不超过32位）
            base_out_trade_no = self.payment_service.generate_out_trade_no(user_id)
            # 添加BOOKING前缀，但确保总长度不超过32位
            out_trade_no = f"BOOKING{base_out_trade_no}"[:32]
            print(f"[DEBUG] 预订时生成的商户订单号: {out_trade_no}")
            
            # 创建支付订单并关联到预订
            from app.models.schemas import PaymentOrderCreate
            payment_order_data = PaymentOrderCreate(
                user_id=user_id,
                openid="",  # openid将在支付时更新
                out_trade_no=out_trade_no,
                body=f"棋牌室预订-{room.name}",
                total_fee=int(final_amount * 100),  # 转换为分
                status=PaymentStatusEnum.PENDING,
                transaction_id=None,
                ip_address=None
            )
            
            # 创建支付订单
            payment_order = self.payment_service.create_payment_order(payment_order_data, allow_duplicate=True)
            
            # 关联预订和支付订单
            booking.payment_order_id = payment_order.id
            
            self.db.commit()
            
            print(f"成功创建预订: 预订ID {booking.id}, 支付订单ID {payment_order.id}, 商户订单号 {out_trade_no}")
            
            return {
                'success': True,
                'message': '预订创建成功',
                'data': {
                    'booking_id': booking.id,
                    'out_trade_no': out_trade_no,
                    'amount': final_amount,
                    'payment_order_id': payment_order.id
                }
            }
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"创建预订失败: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"创建预订失败: {str(e)}"
            )
    
    def _create_booking_time_slots(self, booking: Booking, booking_data: BookingCreate):
        """创建预订时间段详细记录"""
        try:
            # 生成每小时的时间段记录
            start_time = datetime.fromtimestamp(booking_data.start_time)
            end_time = datetime.fromtimestamp(booking_data.end_time)
            
            current_time = start_time
            while current_time < end_time:
                next_time = current_time + timedelta(hours=1)
                if next_time > end_time:
                    next_time = end_time
                    
                time_slot = BookingTimeSlot(
                    booking_id=booking.id,
                    room_id=booking.room_id,
                    date=current_time.date(),
                    hour=current_time.hour,
                    timestamp_start=int(current_time.timestamp()),
                    timestamp_end=int(next_time.timestamp())
                )
                self.db.add(time_slot)
                current_time = next_time
                
        except Exception as e:
            logger.error(f"创建时间段记录失败: {str(e)}")
            # 不抛出异常，因为这是辅助功能
    
    def get_user_bookings(self, user_id: int, skip: int = 0, limit: int = 100, filters: Optional[Any] = None) -> List[Any]:
        """获取用户的所有预订"""
        from app.models.schemas import BookingResponse, BookingStatusEnum as SchemaBookingStatusEnum
        
        query = self.db.query(Booking).filter(Booking.user_id == user_id)
        
        # Apply filters if provided
        if filters:
            if filters.status:
                query = query.filter(Booking.status == filters.status)
            if filters.room_id:
                query = query.filter(Booking.room_id == filters.room_id)
                
        bookings = query.offset(skip).limit(limit).all()
        
        # 转换为 BookingResponse 对象
        result = []
        for booking in bookings:
            # 将数据库的 BookingStatusEnum 转换为 schemas 的 BookingStatusEnum
            # 添加更健壮的错误处理，处理空值和无效值
            db_status = booking.status
            print(f"[DEBUG] get_user_bookings - booking.id: {booking.id}, db_status: '{db_status}', type: {type(db_status)}")
            
            # 处理空值或无效状态
            if not db_status or db_status.strip() == '':
                print(f"[DEBUG] 状态值为空或无效: '{db_status}', 使用默认状态 PENDING")
                status_str = "pending"
                db_status = BookingStatusEnum.PENDING
            else:
                try:
                    # 直接使用字符串值，避免枚举转换问题
                    status_str = db_status
                    print(f"[DEBUG] get_user_bookings - booking.id: {booking.id}, status_str: {status_str}")
                except (ValueError, TypeError) as e:
                    # 如果转换失败，使用默认状态
                    print(f"[DEBUG] 无法处理状态值: '{db_status}', 错误: {e}, 使用默认状态 PENDING")
                    status_str = "pending"
                    db_status = BookingStatusEnum.PENDING  # 同时更新数据库状态值用于后续比较
            
            # 创建 BookingResponse 前添加详细调试信息
            print(f"[DEBUG] 创建 BookingResponse 前 - status_str: '{status_str}', type: {type(status_str)}")
            
            booking_response = BookingResponse(
                id=booking.id,
                user_id=booking.user_id,
                room_id=booking.room_id,
                room_name=booking.room.name if booking.room else '',
                store_name=booking.room.store.name if booking.room and booking.room.store else '',
                room_image=None,
                booking_date=booking.booking_date.strftime('%Y-%m-%d') if booking.booking_date else '',
                start_time=booking.start_time,
                end_time=booking.end_time,
                duration=booking.duration,
                contact_name=booking.contact_name,
                contact_phone=booking.contact_phone,
                remark=booking.remark,
                original_amount=booking.original_amount,
                discount_amount=booking.discount_amount,
                final_amount=booking.final_amount,
                status=status_str,
                payment_order_id=booking.payment_order_id,
                created_at=booking.created_at.isoformat() if booking.created_at else '',
                updated_at=booking.updated_at.isoformat() if booking.updated_at else '',
                can_cancel=db_status == BookingStatusEnum.PENDING,
                can_pay=db_status == BookingStatusEnum.PENDING,
                can_rate=db_status == BookingStatusEnum.COMPLETED
            )
            
            # 创建 BookingResponse 后添加详细调试信息
            print(f"[DEBUG] 创建 BookingResponse 后 - booking_response.status: '{booking_response.status}', type: {type(booking_response.status)}")
            result.append(booking_response)
        
        return result
    
    def get_booking(self, booking_id: int, user_id: int) -> Any:
        """获取特定预订"""
        from app.models.schemas import BookingResponse, BookingStatusEnum as SchemaBookingStatusEnum
        
        booking = self.db.query(Booking).filter(
            and_(Booking.id == booking_id, Booking.user_id == user_id)
        ).first()
        
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="预订不存在"
            )
        
        # 处理状态字段，使用字符串值避免枚举序列化问题
        # 添加更健壮的错误处理，处理空值和无效值
        db_status = booking.status
        print(f"[DEBUG] get_booking - booking.id: {booking.id}, db_status: '{db_status}', type: {type(db_status)}")
        
        # 处理空值或无效状态
        if not db_status or db_status.strip() == '':
            print(f"[DEBUG] 状态值为空或无效: '{db_status}', 使用默认状态 PENDING")
            status_str = "pending"
            db_status = BookingStatusEnum.PENDING
        else:
            try:
                # 直接使用字符串值，避免枚举转换问题
                status_str = db_status
                print(f"[DEBUG] get_booking - booking.id: {booking.id}, status_str: {status_str}")
            except (ValueError, TypeError) as e:
                # 如果转换失败，使用默认状态
                print(f"[DEBUG] 无法处理状态值: '{db_status}', 错误: {e}, 使用默认状态 PENDING")
                status_str = "pending"
                db_status = BookingStatusEnum.PENDING  # 同时更新数据库状态值用于后续比较
        
        # 转换为 BookingResponse 对象
        booking_response = BookingResponse(
            id=booking.id,
            user_id=booking.user_id,
            room_id=booking.room_id,
            room_name=booking.room.name if booking.room else '',
            store_name=booking.room.store.name if booking.room and booking.room.store else '',
            room_image=None,
            booking_date=booking.booking_date.strftime('%Y-%m-%d') if booking.booking_date else '',
            start_time=booking.start_time,
            end_time=booking.end_time,
            duration=booking.duration,
            contact_name=booking.contact_name,
            contact_phone=booking.contact_phone,
            remark=booking.remark,
            original_amount=booking.original_amount,
            discount_amount=booking.discount_amount,
            final_amount=booking.final_amount,
            status=status_str,
            payment_order_id=booking.payment_order_id,
            created_at=booking.created_at.isoformat() if booking.created_at else '',
            updated_at=booking.updated_at.isoformat() if booking.updated_at else '',
            can_cancel=db_status == BookingStatusEnum.PENDING,
            can_pay=db_status == BookingStatusEnum.PENDING,
            can_rate=db_status == BookingStatusEnum.COMPLETED
        )
        
        return booking_response
    
    def update_booking(self, booking_id: int, booking_data: BookingUpdate, user_id: int) -> Any:
        """更新预订"""
        from app.models.schemas import BookingResponse, BookingStatusEnum as SchemaBookingStatusEnum
        
        # 获取数据库中的预订对象
        db_booking = self.db.query(Booking).filter(
            and_(Booking.id == booking_id, Booking.user_id == user_id)
        ).first()
        
        if not db_booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="预订不存在"
            )
        
        # 只允许更新备注信息
        if booking_data.remark is not None:
            db_booking.remark = booking_data.remark
            
        self.db.commit()
        self.db.refresh(db_booking)
        
        # 将数据库的 BookingStatusEnum 转换为 schemas 的 BookingStatusEnum
        # 添加更健壮的错误处理，处理空值和无效值
        db_status = db_booking.status
        print(f"[DEBUG] update_booking - booking.id: {db_booking.id}, db_status: '{db_status}', type: {type(db_status)}")
        
        # 处理空值或无效状态
        if not db_status or db_status.strip() == '':
            print(f"[DEBUG] 状态值为空或无效: '{db_status}', 使用默认状态 PENDING")
            schema_status = SchemaBookingStatusEnum.PENDING
        else:
            try:
                schema_status = SchemaBookingStatusEnum(db_status)
                print(f"[DEBUG] update_booking - booking.id: {db_booking.id}, schema_status: {schema_status}")
            except (ValueError, TypeError) as e:
                # 如果转换失败，使用默认状态
                print(f"[DEBUG] 无法转换状态值: '{db_status}', 错误: {e}, 使用默认状态 PENDING")
                schema_status = SchemaBookingStatusEnum.PENDING
        
        # 转换为 BookingResponse 对象
        booking_response = BookingResponse(
            id=db_booking.id,
            user_id=db_booking.user_id,
            room_id=db_booking.room_id,
            room_name=db_booking.room.name if db_booking.room else '',
            store_name=db_booking.room.store.name if db_booking.room and db_booking.room.store else '',
            room_image=None,
            booking_date=db_booking.booking_date.strftime('%Y-%m-%d') if db_booking.booking_date else '',
            start_time=db_booking.start_time,
            end_time=db_booking.end_time,
            duration=db_booking.duration,
            contact_name=db_booking.contact_name,
            contact_phone=db_booking.contact_phone,
            remark=db_booking.remark,
            original_amount=db_booking.original_amount,
            discount_amount=db_booking.discount_amount,
            final_amount=db_booking.final_amount,
            status=schema_status,
            payment_order_id=db_booking.payment_order_id,
            created_at=db_booking.created_at.isoformat() if db_booking.created_at else '',
            updated_at=db_booking.updated_at.isoformat() if db_booking.updated_at else '',
            can_cancel=db_booking.status == BookingStatusEnum.PENDING,
            can_pay=db_booking.status == BookingStatusEnum.PENDING,
            can_rate=db_booking.status == BookingStatusEnum.COMPLETED
        )
        
        return booking_response
    
    def cancel_booking(self, booking_id: int, user_id: int) -> Dict[str, Any]:
        """取消预订"""
        booking = self.get_booking(booking_id, user_id)
        
        # 只能取消待确认的预订
        if booking.status != BookingStatusEnum.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能取消待确认的预订"
            )
        
        booking.status = BookingStatusEnum.CANCELLED
        self.db.commit()
        
        return {
            'success': True,
            'message': '预订已取消'
        }
    
    def get_user_pending_bookings(self, user_id: int) -> List[Any]:
        """获取用户的待支付预订列表"""
        from app.models.schemas import BookingResponse, BookingStatusEnum as SchemaBookingStatusEnum
        
        bookings = self.db.query(Booking).filter(
            and_(
                Booking.user_id == user_id,
                Booking.status == BookingStatusEnum.PENDING
            )
        ).all()
        
        # 转换为 BookingResponse 对象
        result = []
        for booking in bookings:
            # 将数据库的 BookingStatusEnum 转换为 schemas 的 BookingStatusEnum
            # 添加更健壮的错误处理，处理空值和无效值
            db_status = booking.status
            print(f"[DEBUG] get_user_pending_bookings - booking.id: {booking.id}, db_status: '{db_status}', type: {type(db_status)}")
            
            # 处理空值或无效状态
            if not db_status or db_status.strip() == '':
                print(f"[DEBUG] 状态值为空或无效: '{db_status}', 使用默认状态 PENDING")
                schema_status = SchemaBookingStatusEnum.PENDING
                db_status = BookingStatusEnum.PENDING
            else:
                try:
                    schema_status = SchemaBookingStatusEnum(db_status)
                    print(f"[DEBUG] get_user_pending_bookings - booking.id: {booking.id}, schema_status: {schema_status}")
                except (ValueError, TypeError) as e:
                    # 如果转换失败，使用默认状态
                    print(f"[DEBUG] 无法转换状态值: '{db_status}', 错误: {e}, 使用默认状态 PENDING")
                    schema_status = SchemaBookingStatusEnum.PENDING
                    db_status = BookingStatusEnum.PENDING  # 同时更新数据库状态值用于后续比较
            
            booking_response = BookingResponse(
                id=booking.id,
                user_id=booking.user_id,
                room_id=booking.room_id,
                room_name=booking.room.name if booking.room else '',
                store_name=booking.room.store.name if booking.room and booking.room.store else '',
                room_image=None,
                booking_date=booking.booking_date.strftime('%Y-%m-%d') if booking.booking_date else '',
                start_time=booking.start_time,
                end_time=booking.end_time,
                duration=booking.duration,
                contact_name=booking.contact_name,
                contact_phone=booking.contact_phone,
                remark=booking.remark,
                original_amount=booking.original_amount,
                discount_amount=booking.discount_amount,
                final_amount=booking.final_amount,
                status=schema_status,
                payment_order_id=booking.payment_order_id,
                created_at=booking.created_at.isoformat() if booking.created_at else '',
                updated_at=booking.updated_at.isoformat() if booking.updated_at else '',
                can_cancel=db_status == BookingStatusEnum.PENDING,
                can_pay=db_status == BookingStatusEnum.PENDING,
                can_rate=db_status == BookingStatusEnum.COMPLETED
            )
            result.append(booking_response)
        
        return result
    
    def get_booking_statistics(self, user_id: int) -> Dict[str, Any]:
        """获取用户的预订统计"""
        total_bookings = self.db.query(Booking).filter(Booking.user_id == user_id).count()
        pending_bookings = self.db.query(Booking).filter(
            and_(Booking.user_id == user_id, Booking.status == BookingStatusEnum.PENDING)
        ).count()
        completed_bookings = self.db.query(Booking).filter(
            and_(Booking.user_id == user_id, Booking.status == BookingStatusEnum.COMPLETED)
        ).count()
        cancelled_bookings = self.db.query(Booking).filter(
            and_(Booking.user_id == user_id, Booking.status == BookingStatusEnum.CANCELLED)
        ).count()
        
        return {
            'total_bookings': total_bookings,
            'pending_bookings': pending_bookings,
            'completed_bookings': completed_bookings,
            'cancelled_bookings': cancelled_bookings
        }
    
    def get_booking_by_id(self, booking_id: int, user_id: int) -> Optional[Booking]:
        """根据ID获取预订"""
        return self.db.query(Booking).filter(
            and_(Booking.id == booking_id, Booking.user_id == user_id)
        ).first()
    
    def update_booking_status(self, booking_id: int, new_status: BookingStatusEnum) -> Dict[str, Any]:
        """更新预订状态（管理员功能）"""
        booking = self.db.query(Booking).filter(Booking.id == booking_id).first()
        
        if not booking:
            return {
                'success': False,
                'message': '预订不存在'
            }
        
        booking.status = new_status
        self.db.commit()
        
        return {
            'success': True,
            'message': '预订状态已更新'
        }