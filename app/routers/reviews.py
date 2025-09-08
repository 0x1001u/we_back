# app/routers/reviews.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.models.database import get_db, User
from app.models.schemas import (
    ReviewCreate, ReviewResponse, ReviewListResponse, PaginationParams,
    APIResponse
)
from app.services.review_service import ReviewService
from app.middleware.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/reviews",
    tags=["reviews"]
)


@router.post("", response_model=APIResponse)
async def create_review(
    review_data: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建评价"""
    review_service = ReviewService(db)
    result = review_service.create_review(current_user.id, review_data)
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result['message']
        )
    
    return APIResponse(
        code=0,
        message=result['message'],
        data=result['data']
    )


@router.get("/me", response_model=ReviewListResponse)
async def get_my_reviews(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页大小"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取我的评价列表"""
    pagination = PaginationParams(page=page, size=size)
    
    review_service = ReviewService(db)
    return review_service.get_user_reviews(current_user.id, pagination)


@router.get("/rooms/{room_id}", response_model=ReviewListResponse)
async def get_room_reviews(
    room_id: int,
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=50, description="每页大小"),
    db: Session = Depends(get_db)
):
    """获取包间评价列表"""
    pagination = PaginationParams(page=page, size=size)
    
    review_service = ReviewService(db)
    return review_service.get_room_reviews(room_id, pagination)


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review_detail(
    review_id: int,
    db: Session = Depends(get_db)
):
    """获取评价详情"""
    review_service = ReviewService(db)
    review = review_service.get_review_by_id(review_id)
    
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="评价不存在"
        )
    
    return review


@router.post("/{review_id}/reply", response_model=APIResponse)
async def reply_review(
    review_id: int,
    reply_content: str = Query(..., min_length=1, max_length=500, description="回复内容"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """商家回复评价（管理员功能）"""
    # 这里可以添加管理员权限检查
    # if not is_admin_user(current_user.id, db):
    #     raise HTTPException(status_code=403, detail="权限不足")
    
    review_service = ReviewService(db)
    result = review_service.reply_review(review_id, reply_content)
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result['message']
        )
    
    return APIResponse(
        code=0,
        message=result['message']
    )


@router.get("/statistics/room/{room_id}")
async def get_room_review_statistics(
    room_id: int,
    db: Session = Depends(get_db)
):
    """获取包间评价统计"""
    review_service = ReviewService(db)
    return review_service.get_review_statistics(room_id)


@router.get("/statistics/overall")
async def get_overall_review_statistics(
    db: Session = Depends(get_db)
):
    """获取整体评价统计"""
    review_service = ReviewService(db)
    return review_service.get_review_statistics()


@router.get("/check/booking/{booking_id}")
async def check_can_review_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """检查是否可以对预订进行评价"""
    review_service = ReviewService(db)
    can_review = review_service.can_user_review_booking(current_user.id, booking_id)
    
    return {
        "can_review": can_review
    }