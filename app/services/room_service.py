# app/services/room_service.py
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc
from datetime import datetime, date, timedelta
import json

from app.models.database import Store, Room, Booking, Review
from app.models.schemas import (
    StoreResponse, RoomResponse, RoomListResponse, RoomFilterParams,
    AvailabilityResponse, AvailableTimeSlot, PaginationParams
)


class RoomService:
    """包间服务类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_store_info(self) -> Optional[StoreResponse]:
        """获取店面信息"""
        store = self.db.query(Store).filter(Store.is_active == True).first()
        if not store:
            return None
        
        # 转换为响应模型
        return StoreResponse.model_validate(store)
    
    def get_rooms(
        self, 
        pagination: PaginationParams,
        filters: Optional[RoomFilterParams] = None
    ) -> RoomListResponse:
        """获取包间列表"""
        query = self.db.query(Room).filter(Room.is_available == True)
        
        # 应用过滤条件
        if filters:
            if filters.store_id:
                query = query.filter(Room.store_id == filters.store_id)
            if filters.min_price is not None:
                query = query.filter(Room.price >= filters.min_price)
            if filters.max_price is not None:
                query = query.filter(Room.price <= filters.max_price)
            if filters.is_available is not None:
                query = query.filter(Room.is_available == filters.is_available)
        
        # 获取总数
        total = query.count()
        
        # 分页查询
        rooms = query.order_by(Room.price.asc()).offset(
            (pagination.page - 1) * pagination.size
        ).limit(pagination.size).all()
        
        # 计算总页数
        pages = (total + pagination.size - 1) // pagination.size
        
        # 转换为响应模型
        room_responses = []
        for room in rooms:
            # 手动构建 RoomResponse 对象
            room_data = {
                'id': room.id,
                'store_id': room.store_id,
                'name': room.name,
                'capacity': room.capacity,
                'price': room.price,
                'unit': room.unit,
                'discount': room.discount,
                'images': room.images,
                'features': room.features,
                'facilities': room.facilities,
                'description': room.description,
                'booking_rules': room.booking_rules,
                'rating': room.rating,
                'review_count': room.review_count,
                'is_available': room.is_available,
                'created_at': room.created_at,
                'updated_at': room.updated_at
            }
            room_responses.append(RoomResponse(**room_data))
        
        return RoomListResponse(
            rooms=room_responses,
            total=total,
            page=pagination.page,
            size=pagination.size,
            pages=pages
        )
    
    def get_room_by_id(self, room_id: int) -> Optional[RoomResponse]:
        """根据ID获取包间详情"""
        room = self.db.query(Room).options(
            joinedload(Room.store),
            joinedload(Room.reviews)
        ).filter(Room.id == room_id).first()
        
        if not room:
            return None
        
        # 手动构建 RoomResponse 对象
        room_data = {
            'id': room.id,
            'store_id': room.store_id,
            'name': room.name,
            'capacity': room.capacity,
            'price': room.price,
            'unit': room.unit,
            'discount': room.discount,
            'images': room.images,
            'features': room.features,
            'facilities': room.facilities,
            'description': room.description,
            'booking_rules': room.booking_rules,
            'rating': room.rating,
            'review_count': room.review_count,
            'is_available': room.is_available,
            'created_at': room.created_at,
            'updated_at': room.updated_at
        }
        return RoomResponse(**room_data)
    
    def get_room_availability(
        self, 
        room_id: int, 
        check_date: str
    ) -> Optional[AvailabilityResponse]:
        """获取包间指定日期的可用时间段"""
        # 验证包间是否存在
        room = self.db.query(Room).filter(Room.id == room_id).first()
        if not room:
            return None
        
        try:
            check_datetime = datetime.strptime(check_date, '%Y-%m-%d').date()
        except ValueError:
            return None
        
        # 获取当前日期已有的预订
        existing_bookings = self.db.query(Booking).filter(
            and_(
                Booking.room_id == room_id,
                func.date(Booking.booking_date) == check_datetime,
                Booking.status.in_(['confirmed', 'using'])
            )
        ).all()
        
        # 生成时间段列表（9:00-23:00）
        time_slots = []
        for hour in range(9, 23):
            time_str = f"{hour:02d}:00"
            
            # 检查这个时间段是否被预订
            is_available = True
            for booking in existing_bookings:
                # 将时间戳转换为小时数进行比较
                start_hour = datetime.fromtimestamp(booking.start_time).hour
                end_hour = datetime.fromtimestamp(booking.end_time).hour
                
                # 处理跨天情况
                if start_hour <= end_hour:
                    # 普通情况（不跨天）
                    if start_hour <= hour < end_hour:
                        is_available = False
                        break
                else:
                    # 跨天情况
                    if hour >= start_hour or hour < end_hour:
                        is_available = False
                        break
            
            time_slots.append(AvailableTimeSlot(
                time=time_str,
                available=is_available
            ))
        
        return AvailabilityResponse(
            date=check_date,
            time_slots=time_slots
        )
    
    def get_room_reviews(
        self, 
        room_id: int,
        pagination: PaginationParams
    ) -> Dict[str, Any]:
        """获取包间评价列表"""
        query = self.db.query(Review).options(
            joinedload(Review.user)
        ).filter(Review.room_id == room_id)
        
        # 获取总数
        total = query.count()
        
        # 分页查询
        reviews = query.order_by(desc(Review.created_at)).offset(
            (pagination.page - 1) * pagination.size
        ).limit(pagination.size).all()
        
        # 计算总页数
        pages = (total + pagination.size - 1) // pagination.size
        
        # 构建响应数据
        review_responses = []
        for review in reviews:
            review_data = {
                'id': review.id,
                'user_id': review.user_id,
                'user_name': review.user.nickname if review.user.nickname else '匿名用户',
                'user_avatar': review.user.avatar_url,
                'room_id': review.room_id,
                'booking_id': review.booking_id,
                'rating': review.rating,
                'content': review.content,
                'images': json.loads(review.images) if review.images else [],
                'reply': review.reply,
                'reply_at': review.reply_at.isoformat() if review.reply_at else None,
                'is_anonymous': review.is_anonymous,
                'created_at': review.created_at.isoformat(),
                'updated_at': review.updated_at.isoformat()
            }
            review_responses.append(review_data)
        
        return {
            'reviews': review_responses,
            'total': total,
            'page': pagination.page,
            'size': pagination.size,
            'pages': pages
        }
    
    def search_rooms(
        self, 
        keyword: str,
        pagination: PaginationParams
    ) -> RoomListResponse:
        """搜索包间"""
        query = self.db.query(Room).filter(
            and_(
                Room.is_available == True,
                or_(
                    Room.name.contains(keyword),
                    Room.description.contains(keyword),
                    Room.features.contains(keyword)
                )
            )
        )
        
        # 获取总数
        total = query.count()
        
        # 分页查询
        rooms = query.order_by(Room.rating.desc()).offset(
            (pagination.page - 1) * pagination.size
        ).limit(pagination.size).all()
        
        # 计算总页数
        pages = (total + pagination.size - 1) // pagination.size
        
        # 转换为响应模型
        room_responses = []
        for room in rooms:
            # 手动构建 RoomResponse 对象
            room_data = {
                'id': room.id,
                'store_id': room.store_id,
                'name': room.name,
                'capacity': room.capacity,
                'price': room.price,
                'unit': room.unit,
                'discount': room.discount,
                'images': room.images,
                'features': room.features,
                'facilities': room.facilities,
                'description': room.description,
                'booking_rules': room.booking_rules,
                'rating': room.rating,
                'review_count': room.review_count,
                'is_available': room.is_available,
                'created_at': room.created_at,
                'updated_at': room.updated_at
            }
            room_responses.append(RoomResponse(**room_data))
        
        return RoomListResponse(
            rooms=room_responses,
            total=total,
            page=pagination.page,
            size=pagination.size,
            pages=pages
        )
    
    def get_recommended_rooms(self, limit: int = 6) -> List[RoomResponse]:
        """获取推荐包间"""
        rooms = self.db.query(Room).filter(
            Room.is_available == True
        ).order_by(
            desc(Room.rating),
            desc(Room.review_count)
        ).limit(limit).all()
        
        # 转换为响应模型
        room_responses = []
        for room in rooms:
            # 手动构建 RoomResponse 对象
            room_data = {
                'id': room.id,
                'store_id': room.store_id,
                'name': room.name,
                'capacity': room.capacity,
                'price': room.price,
                'unit': room.unit,
                'discount': room.discount,
                'images': room.images,
                'features': room.features,
                'facilities': room.facilities,
                'description': room.description,
                'booking_rules': room.booking_rules,
                'rating': room.rating,
                'review_count': room.review_count,
                'is_available': room.is_available,
                'created_at': room.created_at,
                'updated_at': room.updated_at
            }
            room_responses.append(RoomResponse(**room_data))
        
        return room_responses
    
    def get_room_availability_extended(
        self,
        room_id: int,
        start_date: Optional[str] = None,
        days: int = 3
    ) -> Dict[str, Any]:
        """获取包间多天的可用性数据（新版，基于BookingTimeSlot表）"""
        try:
            from app.models.schemas import HourlyAvailability, RoomAvailabilityResponse
            from sqlalchemy import inspect
            
            print(f"查询包间可用性: room_id={room_id}, start_date={start_date}, days={days}")
            
            # 验证包间是否存在
            room = self.db.query(Room).filter(Room.id == room_id).first()
            if not room:
                raise ValueError("包间不存在")
            
            # 处理开始日期
            if start_date:
                try:
                    start_datetime = datetime.strptime(start_date, '%Y-%m-%d').date()
                except ValueError:
                    raise ValueError("日期格式错误，请使用 YYYY-MM-DD 格式")
            else:
                start_datetime = datetime.now().date()
            
            # 生成日期列表
            dates = [start_datetime + timedelta(days=i) for i in range(days)]
            
            # 检查BookingTimeSlot表是否存在
            inspector = inspect(self.db.bind)
            has_booking_time_slots = inspector.has_table('booking_time_slots')
            
            print(f"BookingTimeSlot表是否存在: {has_booking_time_slots}")
            
            if has_booking_time_slots:
                # 使用新的BookingTimeSlot表查询
                return self._get_availability_with_time_slots(room_id, start_datetime, days, dates)
            else:
                # 使用原来的Booking表查询
                return self._get_availability_with_bookings(room_id, start_datetime, days, dates)
                
        except Exception as e:
            print(f"查询包间可用性失败: {str(e)}")
            import traceback
            traceback.print_exc()
            raise e
    
    def _get_availability_with_time_slots(
        self, 
        room_id: int, 
        start_datetime: datetime.date, 
        days: int, 
        dates: list
    ) -> Dict[str, Any]:
        """使用BookingTimeSlot表查询可用性"""
        try:
            from app.models.schemas import HourlyAvailability, RoomAvailabilityResponse
            from app.models.database import BookingTimeSlot, Booking
            from sqlalchemy import and_
            
            print(f"使用BookingTimeSlot表查询可用性")
            
            # 获取房间信息
            room = self.db.query(Room).filter(Room.id == room_id).first()
            if not room:
                raise ValueError("包间不存在")
            
            # 使用BookingTimeSlot表查询已占用的时间段
            occupied_slots = self.db.query(BookingTimeSlot).join(Booking).filter(
                and_(
                    BookingTimeSlot.room_id == room_id,
                    BookingTimeSlot.date.in_(dates),
                    Booking.status.in_(['confirmed', 'using'])
                )
            ).all()
            
            # 生成每小时可用性数据
            availability_hours = []
            
            for current_date in dates:
                for hour in range(0, 24):  # 0-23小时
                    time_str = f"{hour:02d}:00"
                    datetime_display = f"{current_date.strftime('%m-%d')} {time_str}"
                    
                    # 检查该小时是否被占用
                    is_occupied = any(
                        slot.date == current_date and slot.hour == hour 
                        for slot in occupied_slots
                    )
                    
                    # 检查是否可作为开始时间（需要连续4小时空闲）
                    can_start = False
                    booking_id = None
                    
                    if not is_occupied:
                        # 检查后续3小时是否也空闲
                        consecutive_free = 1  # 当前小时已经是空闲的
                        
                        for offset in range(1, 4):  # 检查后续3小时
                            check_hour = hour + offset
                            check_date = current_date
                            
                            # 处理跨天情况
                            if check_hour >= 24:
                                check_hour -= 24
                                check_date = current_date + timedelta(days=1)
                                
                                # 如果超出查询范围，停止检查
                                if check_date not in dates:
                                    break
                            
                            # 检查这个小时是否被占用
                            hour_occupied = any(
                                slot.date == check_date and slot.hour == check_hour 
                                for slot in occupied_slots
                            )
                            
                            if hour_occupied:
                                break
                            consecutive_free += 1
                        
                        can_start = consecutive_free >= 4
                    else:
                        # 找到占用该时间段的预订ID
                        occupied_slot = next(
                            (slot for slot in occupied_slots 
                             if slot.date == current_date and slot.hour == hour), 
                            None
                        )
                        if occupied_slot:
                            booking_id = occupied_slot.booking_id
                    
                    # 确定状态颜色
                    if is_occupied:
                        status_color = "red"
                    elif can_start:
                        status_color = "green"
                    else:
                        status_color = "yellow"
                    
                    availability_hours.append(HourlyAvailability(
                        hour=time_str,
                        date=current_date.strftime('%Y-%m-%d'),
                        datetime_display=datetime_display,
                        is_occupied=is_occupied,
                        can_start=can_start,
                        status_color=status_color,
                        booking_id=booking_id
                    ))
            
            # 格式化现有预订数据（基于BookingTimeSlot的分组）
            booking_data = []
            processed_bookings = set()
            
            for slot in occupied_slots:
                if slot.booking_id not in processed_bookings:
                    booking = slot.booking
                    if booking:
                        booking_data.append({
                            "id": booking.id,
                            "start_time": booking.start_time,
                            "end_time": booking.end_time,
                            "duration": booking.duration,
                            "status": booking.status
                        })
                        processed_bookings.add(slot.booking_id)
            
            return RoomAvailabilityResponse(
                room_id=room_id,
                room_name=room.name,
                availability_hours=availability_hours,
                existing_bookings=booking_data
            ).dict()
            
        except Exception as e:
            print(f"_get_availability_with_time_slots 失败: {str(e)}")
            import traceback
            traceback.print_exc()
            raise e
    
    def _get_availability_with_bookings(
        self, 
        room_id: int, 
        start_datetime: datetime.date, 
        days: int, 
        dates: list
    ) -> Dict[str, Any]:
        """使用原来的Booking表查询可用性（向后兼容）"""
        try:
            from app.models.schemas import HourlyAvailability, RoomAvailabilityResponse
            from app.models.database import Booking
            from sqlalchemy import func, and_, or_
            
            print(f"使用原来的Booking表查询可用性")
            
            # 获取房间信息
            room = self.db.query(Room).filter(Room.id == room_id).first()
            if not room:
                raise ValueError("包间不存在")
            
            # 获取所有相关预订记录
            existing_bookings = self.db.query(Booking).filter(
                and_(
                    Booking.room_id == room_id,
                    func.date(Booking.booking_date).in_(dates),
                    Booking.status.in_(['confirmed', 'using'])
                )
            ).all()
            
            print(f"找到 {len(existing_bookings)} 个相关预订")
            
            # 生成每小时可用性数据
            availability_hours = []
            
            for current_date in dates:
                # 获取当天的预订
                day_bookings = [
                    booking for booking in existing_bookings 
                    if booking.booking_date.date() == current_date
                ]
                
                for hour in range(0, 24):  # 0-23小时
                    time_str = f"{hour:02d}:00"
                    datetime_display = f"{current_date.strftime('%m-%d')} {time_str}"
                    
                    # 检查该小时是否被占用
                    is_occupied = False
                    booking_id = None
                    
                    for booking in day_bookings:
                        # 使用时间戳进行时间比较
                        start_dt = datetime.fromtimestamp(booking.start_time)
                        end_dt = datetime.fromtimestamp(booking.end_time)
                        
                        # 获取小时数
                        start_hour = start_dt.hour
                        end_hour = end_dt.hour
                        
                        # 检查是否跨天
                        if start_dt.date() != end_dt.date():
                            # 跨天情况
                            if start_dt.date() == current_date:
                                # 当天的开始部分
                                if hour >= start_hour:
                                    is_occupied = True
                                    booking_id = booking.id
                                    break
                            elif end_dt.date() == current_date:
                                # 次日的结束部分
                                if hour < end_hour:
                                    is_occupied = True
                                    booking_id = booking.id
                                    break
                        else:
                            # 普通情况（不跨天）
                            if start_hour <= hour < end_hour:
                                is_occupied = True
                                booking_id = booking.id
                                break
                    
                    # 检查是否可作为开始时间（需要连续4小时空闲）
                    can_start = False
                    if not is_occupied:
                        consecutive_free = 0
                        for check_hour in range(hour, hour + 4):
                            # 跨天检查
                            check_date = current_date
                            check_hour_actual = check_hour
                            
                            if check_hour >= 24:
                                check_date = current_date + timedelta(days=1)
                                check_hour_actual = check_hour - 24
                                
                                # 如果超出查询范围，停止检查
                                if check_date not in dates:
                                    break
                            
                            # 检查这个小时是否被占用
                            hour_occupied = False
                            check_day_bookings = [
                                b for b in existing_bookings 
                                if b.booking_date.date() == check_date
                            ]
                            
                            for booking in check_day_bookings:
                                start_dt = datetime.fromtimestamp(booking.start_time)
                                end_dt = datetime.fromtimestamp(booking.end_time)
                                start_hour = start_dt.hour
                                end_hour = end_dt.hour
                                
                                if start_dt.date() != end_dt.date():
                                    # 跨天情况
                                    if start_dt.date() == check_date:
                                        if check_hour_actual >= start_hour:
                                            hour_occupied = True
                                            break
                                    elif end_dt.date() == check_date:
                                        if check_hour_actual < end_hour:
                                            hour_occupied = True
                                            break
                                else:
                                    # 普通情况
                                    if start_hour <= check_hour_actual < end_hour:
                                        hour_occupied = True
                                        break
                            
                            if hour_occupied:
                                break
                            consecutive_free += 1
                        
                        can_start = consecutive_free >= 4
                    
                    # 确定状态颜色
                    if is_occupied:
                        status_color = "red"
                    elif can_start:
                        status_color = "green"
                    else:
                        status_color = "yellow"
                    
                    availability_hours.append(HourlyAvailability(
                        hour=time_str,
                        date=current_date.strftime('%Y-%m-%d'),
                        datetime_display=datetime_display,
                        is_occupied=is_occupied,
                        can_start=can_start,
                        status_color=status_color,
                        booking_id=booking_id
                    ))
            
            # 格式化现有预订数据
            booking_data = []
            for booking in existing_bookings:
                booking_data.append({
                    "id": booking.id,
                    "start_time": booking.start_time,
                    "end_time": booking.end_time,
                    "duration": booking.duration,
                    "status": booking.status
                })
                
            return RoomAvailabilityResponse(
                room_id=room_id,
                room_name=room.name,
                availability_hours=availability_hours,
                existing_bookings=booking_data
            ).dict()
            
        except Exception as e:
            print(f"_get_availability_with_bookings 失败: {str(e)}")
            import traceback
            traceback.print_exc()
            raise e
