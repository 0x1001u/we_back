# app/services/review_service.py
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, desc
from datetime import datetime
import json

from app.models.database import Review, Booking, Room, User
from app.models.schemas import (
    ReviewCreate, ReviewResponse, ReviewListResponse, PaginationParams,
    BookingStatusEnum
)


class ReviewService:
    """评价服务类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_review(
        self, 
        user_id: int, 
        review_data: ReviewCreate
    ) -> Dict[str, Any]:
        """创建评价"""
        # 验证预订是否存在且属于当前用户
        booking = self.db.query(Booking).filter(
            and_(
                Booking.id == review_data.booking_id,
                Booking.user_id == user_id,
                Booking.status == BookingStatusEnum.COMPLETED
            )
        ).first()
        
        if not booking:
            return {
                'success': False,
                'message': '预订不存在或状态不允许评价'
            }
        
        # 检查是否已经评价过
        existing_review = self.db.query(Review).filter(
            Review.booking_id == review_data.booking_id
        ).first()
        
        if existing_review:
            return {
                'success': False,
                'message': '该预订已经评价过了'
            }
        
        # 创建评价记录
        review = Review(
            user_id=user_id,
            room_id=booking.room_id,
            booking_id=review_data.booking_id,
            rating=review_data.rating,
            content=review_data.content,
            images=json.dumps(review_data.images) if review_data.images else None,
            is_anonymous=review_data.is_anonymous
        )
        
        self.db.add(review)
        
        # 更新包间的评分和评价数量
        self._update_room_rating(booking.room_id)
        
        self.db.commit()
        
        return {
            'success': True,
            'message': '评价提交成功',
            'data': {
                'review_id': review.id
            }
        }
    
    def get_room_reviews(
        self,
        room_id: int,
        pagination: PaginationParams
    ) -> ReviewListResponse:
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
        
        # 转换为响应模型
        review_responses = []
        for review in reviews:
            review_data = self._build_review_response(review)
            review_responses.append(review_data)
        
        return ReviewListResponse(
            reviews=review_responses,
            total=total,
            page=pagination.page,
            size=pagination.size,
            pages=pages
        )
    
    def get_user_reviews(
        self,
        user_id: int,
        pagination: PaginationParams
    ) -> ReviewListResponse:
        """获取用户评价列表"""
        query = self.db.query(Review).options(
            joinedload(Review.room),
            joinedload(Review.user)
        ).filter(Review.user_id == user_id)
        
        # 获取总数
        total = query.count()
        
        # 分页查询
        reviews = query.order_by(desc(Review.created_at)).offset(
            (pagination.page - 1) * pagination.size
        ).limit(pagination.size).all()
        
        # 计算总页数
        pages = (total + pagination.size - 1) // pagination.size
        
        # 转换为响应模型
        review_responses = []
        for review in reviews:
            review_data = self._build_review_response(review)
            review_responses.append(review_data)
        
        return ReviewListResponse(
            reviews=review_responses,
            total=total,
            page=pagination.page,
            size=pagination.size,
            pages=pages
        )
    
    def get_review_by_id(self, review_id: int) -> Optional[ReviewResponse]:
        """根据ID获取评价详情"""
        review = self.db.query(Review).options(
            joinedload(Review.user),
            joinedload(Review.room)
        ).filter(Review.id == review_id).first()
        
        if not review:
            return None
        
        return self._build_review_response(review)
    
    def reply_review(
        self, 
        review_id: int, 
        reply_content: str
    ) -> Dict[str, Any]:
        """商家回复评价"""
        review = self.db.query(Review).filter(Review.id == review_id).first()
        
        if not review:
            return {
                'success': False,
                'message': '评价不存在'
            }
        
        if review.reply:
            return {
                'success': False,
                'message': '该评价已经回复过了'
            }
        
        review.reply = reply_content
        review.reply_at = datetime.utcnow()
        review.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        return {
            'success': True,
            'message': '回复成功'
        }
    
    def get_review_statistics(self, room_id: Optional[int] = None) -> Dict[str, Any]:
        """获取评价统计"""
        query = self.db.query(Review)
        
        if room_id:
            query = query.filter(Review.room_id == room_id)
        
        total_reviews = query.count()
        
        if total_reviews == 0:
            return {
                'total': 0,
                'average_rating': 0,
                'rating_distribution': {
                    '5': 0, '4': 0, '3': 0, '2': 0, '1': 0
                }
            }
        
        # 计算平均评分
        average_rating = query.with_entities(func.avg(Review.rating)).scalar()
        
        # 计算评分分布
        rating_distribution = {}
        for rating in range(1, 6):
            count = query.filter(Review.rating == rating).count()
            rating_distribution[str(rating)] = count
        
        return {
            'total': total_reviews,
            'average_rating': round(float(average_rating), 2) if average_rating else 0,
            'rating_distribution': rating_distribution
        }
    
    def can_user_review_booking(self, user_id: int, booking_id: int) -> bool:
        """检查用户是否可以对预订进行评价"""
        # 检查预订是否存在且属于用户
        booking = self.db.query(Booking).filter(
            and_(
                Booking.id == booking_id,
                Booking.user_id == user_id,
                Booking.status == BookingStatusEnum.COMPLETED
            )
        ).first()
        
        if not booking:
            return False
        
        # 检查是否已经评价过
        existing_review = self.db.query(Review).filter(
            Review.booking_id == booking_id
        ).first()
        
        return existing_review is None
    
    def _update_room_rating(self, room_id: int):
        """更新包间的评分和评价数量"""
        room = self.db.query(Room).filter(Room.id == room_id).first()
        
        if not room:
            return
        
        # 计算新的平均评分和评价数量
        reviews = self.db.query(Review).filter(Review.room_id == room_id).all()
        
        if reviews:
            total_rating = sum(review.rating for review in reviews)
            average_rating = total_rating / len(reviews)
            
            room.rating = round(average_rating, 2)
            room.review_count = len(reviews)
        else:
            room.rating = 5.0  # 默认评分
            room.review_count = 0
        
        room.updated_at = datetime.utcnow()
    
    def _build_review_response(self, review: Review) -> ReviewResponse:
        """构建评价响应数据"""
        # 处理匿名评价
        user_name = "匿名用户"
        user_avatar = None
        
        if not review.is_anonymous and review.user:
            user_name = review.user.nickname if review.user.nickname else "用户"
            user_avatar = review.user.avatar_url
        
        # 解析图片
        images = []
        if review.images:
            try:
                images = json.loads(review.images)
            except (json.JSONDecodeError, TypeError):
                images = []
        
        return ReviewResponse(
            id=review.id,
            user_id=review.user_id,
            user_name=user_name,
            user_avatar=user_avatar,
            room_id=review.room_id,
            booking_id=review.booking_id,
            rating=review.rating,
            content=review.content,
            images=images,
            reply=review.reply,
            reply_at=review.reply_at.isoformat() if review.reply_at else None,
            is_anonymous=review.is_anonymous,
            created_at=review.created_at.isoformat(),
            updated_at=review.updated_at.isoformat()
        )