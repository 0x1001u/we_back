# app/routers/bookings.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.models.database import get_db, User, Booking, BookingStatusEnum as DatabaseBookingStatusEnum
from app.models.schemas import (
    BookingCreate, BookingResponse, BookingListResponse, BookingFilterParams,
    BookingStatusEnum, PaginationParams, APIResponse
)
from app.services.booking_service import BookingService
from app.middleware.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/bookings",
    tags=["bookings"]
)


@router.post("", response_model=APIResponse)
async def create_booking(
    booking_data: BookingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建预订"""
    booking_service = BookingService(db)
    result = booking_service.create_booking(booking_data, current_user.id)
    
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


@router.get("/me", response_model=BookingListResponse)
async def get_my_bookings(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页大小"),
    status: Optional[BookingStatusEnum] = Query(None, description="预订状态"),
    room_id: Optional[int] = Query(None, description="包间ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取我的预订列表"""
    pagination = PaginationParams(page=page, size=size)
    filters = BookingFilterParams(
        status=status,
        room_id=room_id,
        start_date=None,
        end_date=None
    )
    
    booking_service = BookingService(db)
    skip = (pagination.page - 1) * pagination.size
    print(f"[DEBUG] get_my_bookings - user_id: {current_user.id}, skip: {skip}, limit: {pagination.size}, filters: {filters}")
    
    # 使用服务方法获取预订列表
    bookings = booking_service.get_user_bookings(current_user.id, skip, pagination.size, filters)
    
    # 获取总数用于分页
    bookings_query = db.query(Booking).filter(Booking.user_id == current_user.id)
    if filters.status:
        bookings_query = bookings_query.filter(Booking.status == filters.status.value)
    if filters.room_id:
        bookings_query = bookings_query.filter(Booking.room_id == filters.room_id)
    
    total = bookings_query.count()
    
    # 计算总页数
    pages = (total + pagination.size - 1) // pagination.size if total > 0 else 1
    
    return BookingListResponse(
        bookings=bookings,
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=pages
    )


@router.get("/me/pending", response_model=BookingListResponse)
async def get_my_pending_bookings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取我的待支付预订列表"""
    pagination = PaginationParams(page=1, size=100)  # 获取所有待支付订单
    booking_service = BookingService(db)
    
    # 获取用户的所有待支付预订
    pending_bookings = booking_service.get_user_pending_bookings(current_user.id)
    
    # 模拟分页响应结构
    total = len(pending_bookings)
    pages = (total + pagination.size - 1) // pagination.size if total > 0 else 1
    
    return BookingListResponse(
        bookings=pending_bookings,
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=pages
    )


@router.get("/me/statistics")
async def get_my_booking_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取我的预订统计"""
    booking_service = BookingService(db)
    return booking_service.get_booking_statistics(current_user.id)


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking_detail(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取预订详情"""
    booking_service = BookingService(db)
    booking = booking_service.get_booking_by_id(booking_id, current_user.id)
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="预订不存在"
        )
    
    return booking


@router.put("/{booking_id}/cancel", response_model=APIResponse)
async def cancel_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消预订"""
    booking_service = BookingService(db)
    result = booking_service.cancel_booking(booking_id, current_user.id)
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result['message']
        )
    
    return APIResponse(
        code=0,
        message=result['message'],
        data=None
    )


@router.put("/{booking_id}/status", response_model=APIResponse)
async def update_booking_status(
    booking_id: int,
    new_status: BookingStatusEnum,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新预订状态（管理员功能）"""
    # 这里可以添加管理员权限检查
    # if not is_admin_user(current_user.id, db):
    #     raise HTTPException(status_code=403, detail="权限不足")
    
    booking_service = BookingService(db)
    # 将 schemas.BookingStatusEnum 转换为 database.BookingStatusEnum
    db_status = DatabaseBookingStatusEnum(new_status.value)
    result = booking_service.update_booking_status(booking_id, db_status)
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result['message']
        )
    
    return APIResponse(
        code=0,
        message=result['message'],
        data=None
    )