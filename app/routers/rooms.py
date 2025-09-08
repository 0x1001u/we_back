# app/routers/rooms.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
import httpx

from app.models.database import get_db
from app.models.schemas import (
    StoreResponse, RoomResponse, RoomListResponse, RoomFilterParams,
    AvailabilityResponse, PaginationParams, APIResponse,
    RoomAvailabilityResponse, RoomAvailabilityParams,
    DoorOpenRequest, DoorOpenResponse
)
from app.services.room_service import RoomService

router = APIRouter(
    prefix="/api/v1/rooms",
    tags=["rooms"]
)


@router.get("/store", response_model=StoreResponse)
async def get_store_info(db: Session = Depends(get_db)):
    """获取店面信息"""
    room_service = RoomService(db)
    store = room_service.get_store_info()
    
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="店面信息不存在"
        )
    
    return store


@router.get("", response_model=RoomListResponse)
async def get_rooms(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页大小"),
    store_id: Optional[int] = Query(None, description="店面ID"),
    min_price: Optional[float] = Query(None, ge=0, description="最低价格"),
    max_price: Optional[float] = Query(None, ge=0, description="最高价格"),
    is_available: Optional[bool] = Query(None, description="是否可用"),
    db: Session = Depends(get_db)
):
    """获取包间列表"""
    pagination = PaginationParams(page=page, size=size)
    filters = RoomFilterParams(
        store_id=store_id,
        min_price=min_price,
        max_price=max_price,
        is_available=is_available
    )
    
    room_service = RoomService(db)
    return room_service.get_rooms(pagination, filters)


@router.get("/search", response_model=RoomListResponse)
async def search_rooms(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页大小"),
    db: Session = Depends(get_db)
):
    """搜索包间"""
    pagination = PaginationParams(page=page, size=size)
    
    room_service = RoomService(db)
    return room_service.search_rooms(keyword, pagination)


@router.get("/recommended", response_model=list[RoomResponse])
async def get_recommended_rooms(
    limit: int = Query(6, ge=1, le=20, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取推荐包间"""
    room_service = RoomService(db)
    return room_service.get_recommended_rooms(limit)


@router.get("/availability", response_model=RoomAvailabilityResponse)
async def get_room_availability_new(
    room_id: int = Query(..., description="包间ID"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)，默认今天"),
    days: int = Query(3, ge=1, le=7, description="查询天数，默认3天"),
    db: Session = Depends(get_db)
):
    """获取包间可用性数据（新版，支持多天查询）"""
    try:
        print(f"路由层: 查询包间可用性 room_id={room_id}, start_date={start_date}, days={days}")
        
        room_service = RoomService(db)
        
        # 验证包间是否存在
        room = room_service.get_room_by_id(room_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="包间不存在"
            )
        
        # 获取可用性数据
        availability_data = room_service.get_room_availability_extended(
            room_id=room_id,
            start_date=start_date,
            days=days
        )
        return availability_data
        
    except HTTPException:
        raise
    except ValueError as e:
        print(f"路由层: ValueError - {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        print(f"路由层: 未知错误 - {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内部服务器错误: {str(e)}"
        )


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room_detail(
    room_id: int,
    db: Session = Depends(get_db)
):
    """获取包间详情"""
    room_service = RoomService(db)
    room = room_service.get_room_by_id(room_id)
    
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="包间不存在"
        )
    
    return room


@router.get("/{room_id}/availability", response_model=AvailabilityResponse)
async def get_room_availability(
    room_id: int,
    date: str = Query(..., description="查询日期 (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """获取包间可用时间段"""
    room_service = RoomService(db)
    availability = room_service.get_room_availability(room_id, date)
    
    if not availability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="包间不存在或日期格式错误"
        )
    
    return availability


@router.get("/{room_id}/reviews")
async def get_room_reviews(
    room_id: int,
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=50, description="每页大小"),
    db: Session = Depends(get_db)
):
    """获取包间评价列表"""
    pagination = PaginationParams(page=page, size=size)
    
    room_service = RoomService(db)
    return room_service.get_room_reviews(room_id, pagination)
@router.post("/doors", response_model=DoorOpenResponse)
async def open_door(
    request: DoorOpenRequest,
    db: Session = Depends(get_db)
):
    """发送开门指令到外部设备"""
    try:
        # 首先发送门关闭请求
        door_off_url = f"https://3e.upon.ltd/relays/{request.door_id}/off"
        async with httpx.AsyncClient() as client:
            # 发送POST请求关闭门
            door_response = await client.post(door_off_url)
            door_response.raise_for_status()  # 如果响应状态码不是2xx，抛出异常
            
            # 解析门关闭响应
            door_result = door_response.json()
            
            # 验证响应格式
            if "relay_id" not in door_result or "status" not in door_result:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="外部设备响应格式错误"
                )
            
            # 门ID到网关ID的映射
            door_to_gateway = {
                9: 7,
                10: 6,
                11: 8,
                12: 5,
                14: 1,
                15: 2,
                16: 3
            }
            
            # 获取对应的网关ID
            gateway_id = door_to_gateway.get(request.door_id)
            if gateway_id is not None:
                # 检查网关状态
                status_url = f"https://3e.upon.ltd/relays/{gateway_id}/status"
                try:
                    status_response = await client.get(status_url)
                    status_response.raise_for_status()
                    
                    status_result = status_response.json()
                    current_status = status_result.get("status", False)
                    
                    # 如果网关是关闭状态，发送开启指令
                    if not current_status:
                        open_url = f"https://3e.upon.ltd/relays/{gateway_id}/on"
                        await client.post(open_url)
                        # 记录网关被开启，但主要返回门关闭响应
                        print(f"网关 {gateway_id} 已开启")
                
                except httpx.HTTPError as e:
                    # 网关状态检查或开启失败，记录错误但继续返回门关闭响应
                    print(f"网关操作失败: {str(e)}")
            
            return DoorOpenResponse(**door_result)
            
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"外部设备通信失败: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内部服务器错误: {str(e)}"
        )