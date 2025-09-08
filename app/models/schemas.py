from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator, EmailStr


class GenderEnum(int, Enum):
    """性别枚举"""
    UNKNOWN = 0
    MALE = 1
    FEMALE = 2


class UserBase(BaseModel):
    """用户基础模型"""
    nickname: Optional[str] = Field(None, min_length=1, max_length=100, description="用户昵称")
    phone: Optional[str] = Field(None, min_length=11, max_length=20, description="手机号")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    gender: Optional[int] = Field(
        default=GenderEnum.UNKNOWN,
        description="性别：0-未知，1-男，2-女"
    )
    country: Optional[str] = Field(None, max_length=50, description="国家")
    province: Optional[str] = Field(None, max_length=50, description="省份")
    city: Optional[str] = Field(None, max_length=50, description="城市")
    language: Optional[str] = Field(None, max_length=20, description="语言")
    avatar_url: Optional[str] = Field(None, max_length=255, description="头像URL")

    @validator('gender', pre=True)
    def convert_gender(cls, v):
        """统一gender字段为整数类型"""
        if v is None:
            return v
            
        # 处理整数输入
        if isinstance(v, int):
            if v in [0, 1, 2]:
                return v
            return GenderEnum.UNKNOWN
        
        # 处理字符串输入
        if isinstance(v, str):
            if v.isdigit() and int(v) in [0, 1, 2]:
                return int(v)
            try:
                return GenderEnum[v.upper()].value
            except KeyError:
                pass
        
        return GenderEnum.UNKNOWN


class UserCreate(UserBase):
    """创建用户模型"""
    openid: str = Field(..., min_length=1, max_length=64, description="微信openid")
    unionid: Optional[str] = Field(None, max_length=64, description="微信unionid")


class UserUpdate(UserBase):
    """更新用户模型"""
    pass


class UserResponse(UserBase):
    """用户响应模型"""
    id: int
    openid: str
    unionid: Optional[str]
    avatar_url: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str

    @validator('created_at', 'updated_at', pre=True)
    def convert_datetime_to_iso(cls, v):
        """将datetime对象转换为ISO格式字符串"""
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    @validator('nickname', 'avatar_url', 'country', 'province', 'city', pre=True)
    def escape_html(cls, v):
        """HTML转义用户生成内容"""
        if v is None:
            return v
        import html
        return html.escape(v)

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """用户列表响应模型"""
    users: List[UserResponse]
    total: int
    page: int
    size: int
    pages: int


class WechatUserInfo(BaseModel):
    """微信用户信息模型"""
    openid: Optional[str] = Field(None, description="微信openid")
    unionid: Optional[str] = Field(None, description="微信unionid")
    nickname: Optional[str] = Field(None, description="用户昵称", alias="nickName")
    avatar_url: Optional[str] = Field(None, description="头像URL", alias="avatarUrl")
    gender: Optional[int] = Field(
        None,
        description="性别：0-未知，1-男，2-女"
    )
    country: Optional[str] = Field(None, description="国家")
    province: Optional[str] = Field(None, description="省份")
    city: Optional[str] = Field(None, description="城市")
    language: Optional[str] = Field(None, description="语言")

    @validator('gender', pre=True)
    def convert_gender(cls, v):
        """统一gender字段为整数类型"""
        if v is None:
            return v
            
        # 处理整数输入
        if isinstance(v, int):
            if v in [0, 1, 2]:
                return v
            return GenderEnum.UNKNOWN
        
        # 处理字符串输入
        if isinstance(v, str):
            if v.isdigit() and int(v) in [0, 1, 2]:
                return int(v)
            try:
                return GenderEnum[v.upper()].value
            except KeyError:
                pass
        
        return GenderEnum.UNKNOWN

    class Config:
        populate_by_name = True


# ==================== 棋牌室相关模型 ====================

class BookingStatusEnum(str, Enum):
    """预订状态枚举"""
    PENDING = "pending"          # 待支付
    CONFIRMED = "confirmed"      # 已确认
    USING = "using"              # 使用中
    COMPLETED = "completed"      # 已完成
    CANCELLED = "cancelled"      # 已取消


class StoreResponse(BaseModel):
    """店面响应模型"""
    id: int
    name: str
    address: str
    phone: str
    business_hours: str
    rating: float
    image_url: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    features: Optional[List[str]]  # 将JSON字符串转换为List
    description: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str
    
    @validator('created_at', 'updated_at', pre=True)
    def convert_datetime_to_iso(cls, v):
        """将datetime对象转换为ISO格式字符串"""
        if isinstance(v, datetime):
            return v.isoformat()
        return v
        
    @validator('features', pre=True)
    def parse_features(cls, v):
        """解析features JSON字符串"""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v or []
    
    class Config:
        from_attributes = True


class FacilityItem(BaseModel):
    """设施项模型"""
    name: str = Field(..., description="设施名称")
    icon: str = Field(..., description="设施图标")


class RoomResponse(BaseModel):
    """包间响应模型"""
    id: int
    store_id: int
    name: str
    capacity: str
    price: float
    unit: str
    discount: Optional[float]
    current_price: Optional[float] = None  # 计算后的价格
    images: Optional[List[str]]  # 将JSON字符串转换为List
    features: Optional[List[str]]  # 将JSON字符串转换为List
    facilities: Optional[List[FacilityItem]]  # 将JSON字符串转换为List
    description: Optional[str]
    booking_rules: Optional[List[str]]  # 将JSON字符串转换为List
    rating: float
    review_count: int
    is_available: bool
    created_at: str
    updated_at: str
    
    @validator('created_at', 'updated_at', pre=True)
    def convert_datetime_to_iso(cls, v):
        """将datetime对象转换为ISO格式字符串"""
        if isinstance(v, datetime):
            return v.isoformat()
        return v
    
    @validator('current_price', pre=True, always=True)
    def calculate_current_price(cls, v, values):
        """计算当前价格"""
        price = values.get('price', 0)
        discount = values.get('discount')
        if discount and 0 < discount < 1:
            return round(price * discount, 2)
        return price
        
    @validator('images', 'features', 'booking_rules', pre=True)
    def parse_json_list(cls, v):
        """解析JSON字符串为列表"""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v or []
        
    @validator('facilities', pre=True)
    def parse_facilities(cls, v):
        """解析设施JSON字符串"""
        if isinstance(v, str):
            import json
            try:
                facilities_data = json.loads(v)
                return [FacilityItem(**item) for item in facilities_data]
            except (json.JSONDecodeError, TypeError):
                return []
        return v or []
    
    class Config:
        from_attributes = True


class RoomListResponse(BaseModel):
    """包间列表响应模型"""
    rooms: List[RoomResponse]
    total: int
    page: int
    size: int
    pages: int


class BookingCreate(BaseModel):
    """创建预订模型"""
    room_id: int = Field(..., description="包间ID")
    booking_date: str = Field(..., description="预订日期 (YYYY-MM-DD)")
    start_time: int = Field(..., description="开始时间戳（10位秒级）")
    end_time: int = Field(..., description="结束时间戳（10位秒级）")
    duration: int = Field(..., gt=0, description="时长（小时）")
    contact_name: str = Field(..., min_length=1, max_length=50, description="联系人姓名")
    contact_phone: str = Field(..., min_length=11, max_length=20, description="联系电话")
    remark: Optional[str] = Field(None, max_length=500, description="备注信息")
    
    @validator('booking_date')
    def validate_booking_date(cls, v):
        """验证预订日期格式"""
        from datetime import datetime
        try:
            booking_datetime = datetime.strptime(v, '%Y-%m-%d')
            # 检查是否是未来日期
            if booking_datetime.date() < datetime.now().date():
                raise ValueError('预订日期不能是过去的日期')
            return v
        except ValueError as e:
            if '预订日期不能是过去的日期' in str(e):
                raise e
            raise ValueError('日期格式错误，请使用 YYYY-MM-DD 格式')
    
    @validator('start_time', 'end_time')
    def validate_timestamp(cls, v):
        """验证时间戳格式"""
        from datetime import datetime
        
        if not isinstance(v, int):
            raise ValueError('时间必须是10位秒级时间戳')
        
        # 验证时间戳范围（应该在合理范围内）
        try:
            dt = datetime.fromtimestamp(v)
            # 检查时间戳是否在未来的合理范围内（不超过一年）
            now = datetime.now()
            if dt.year < now.year or dt.year > now.year + 1:
                raise ValueError('时间戳超出合理范围')
            return v
        except (ValueError, OSError) as e:
            raise ValueError(f'无效的时间戳: {e}')
    
    @validator('contact_phone')
    def validate_phone(cls, v):
        """验证手机号格式"""
        import re
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('手机号格式错误')
        return v


class BookingTimeSlotResponse(BaseModel):
    """预订时间段响应模型"""
    id: int
    booking_id: int
    room_id: int
    date: str
    hour: int
    timestamp_start: int
    timestamp_end: int
    
    @validator('date', pre=True)
    def convert_date_to_string(cls, v):
        """将日期转换为字符串"""
        if isinstance(v, datetime):
            return v.strftime('%Y-%m-%d')
        return v
    
    class Config:
        from_attributes = True


class BookingResponse(BaseModel):
    """预订响应模型"""
    id: int
    user_id: int
    room_id: int
    room_name: str  # 来自关联查询
    store_name: str  # 来自关联查询
    room_image: Optional[str]  # 来自关联查询
    booking_date: str
    start_time: int  # 开始时间戳
    end_time: int    # 结束时间戳
    duration: int
    contact_name: str
    contact_phone: str
    remark: Optional[str]
    original_amount: float
    discount_amount: float
    final_amount: float
    status: str
    payment_order_id: Optional[int]
    created_at: str
    updated_at: str
    
    # 操作按钮显示控制
    can_cancel: bool = False
    can_pay: bool = False
    can_rate: bool = False
    
    @validator('created_at', 'updated_at', pre=True)
    def convert_datetime_to_iso(cls, v):
        """将datetime对象转换为ISO格式字符串"""
        if isinstance(v, datetime):
            return v.isoformat()
        return v
    
    @validator('booking_date', pre=True)
    def convert_date_to_string(cls, v):
        """将日期转换为字符串"""
        if isinstance(v, datetime):
            return v.strftime('%Y-%m-%d')
        return v
    
    @validator('status', pre=True)
    def validate_status(cls, v):
        """验证状态字段，确保不为空"""
        print(f"[DEBUG] validate_status - input value: {v}, type: {type(v)}")
        
        if v is None:
            print(f"[DEBUG] validate_status - value is None, returning PENDING")
            return BookingStatusEnum.PENDING
        
        # 如果已经是枚举实例，直接返回
        if isinstance(v, BookingStatusEnum):
            print(f"[DEBUG] validate_status - value is already BookingStatusEnum: {v}")
            return v
        
        # 处理字符串
        if isinstance(v, str):
            print(f"[DEBUG] validate_status - value is string: '{v}'")
            if v.strip() == '':
                print(f"[DEBUG] validate_status - string is empty, returning PENDING")
                return BookingStatusEnum.PENDING
            try:
                result = BookingStatusEnum(v)
                print(f"[DEBUG] validate_status - successfully converted string to enum: {result}")
                return result
            except ValueError as e:
                print(f"[DEBUG] validate_status - failed to convert string '{v}': {e}, returning PENDING")
                return BookingStatusEnum.PENDING
        
        # 处理数据库枚举实例
        if hasattr(v, 'value'):
            print(f"[DEBUG] validate_status - value has 'value' attribute: {v}, value: {v.value}")
            try:
                result = BookingStatusEnum(v.value)
                print(f"[DEBUG] validate_status - successfully converted from value: {result}")
                return result
            except ValueError as e:
                print(f"[DEBUG] validate_status - failed to convert from value '{v.value}': {e}, returning PENDING")
                return BookingStatusEnum.PENDING
        
        # 其他情况使用默认值
        print(f"[DEBUG] validate_status - unknown value type, returning PENDING")
        return BookingStatusEnum.PENDING
    
    class Config:
        from_attributes = True
        json_encoders = {
            BookingStatusEnum: lambda v: v.value
        }


class BookingListResponse(BaseModel):
    """预订列表响应模型"""
    bookings: List[BookingResponse]
    total: int
    page: int
    size: int
    pages: int


class BookingFilterParams(BaseModel):
    """预订过滤参数模型"""
    status: Optional[BookingStatusEnum] = Field(None, description="预订状态")
    room_id: Optional[int] = Field(None, description="包间ID")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")


class ReviewCreate(BaseModel):
    """创建评价模型"""
    booking_id: int = Field(..., description="预订ID")
    rating: int = Field(..., ge=1, le=5, description="评分（1-5）")
    content: str = Field(..., min_length=1, max_length=1000, description="评价内容")
    images: Optional[List[str]] = Field(None, description="评价图片URLs")
    is_anonymous: bool = Field(default=False, description="是否匿名")


class ReviewResponse(BaseModel):
    """评价响应模型"""
    id: int
    user_id: int
    user_name: str  # 来自关联查询
    user_avatar: Optional[str]  # 来自关联查询
    room_id: int
    booking_id: int
    rating: int
    content: str
    images: Optional[List[str]]
    reply: Optional[str]
    reply_at: Optional[str]
    is_anonymous: bool


class AvailableTimeSlot(BaseModel):
    """可用时间段模型"""
    time: str = Field(..., description="时间 (HH:MM)")
    available: bool = Field(..., description="是否可用")


class AvailabilityResponse(BaseModel):
    """可用性响应模型"""
    date: str = Field(..., description="日期 (YYYY-MM-DD)")
    time_slots: List[AvailableTimeSlot] = Field(..., description="可用时间段")


class RoomFilterParams(BaseModel):
    """包间过滤参数模型"""
    store_id: Optional[int] = Field(None, description="店面ID")
    min_price: Optional[float] = Field(None, ge=0, description="最低价格")
    max_price: Optional[float] = Field(None, ge=0, description="最高价格")
    is_available: Optional[bool] = Field(None, description="是否可用")


class PaginationParams(BaseModel):
    """分页参数模型"""
    page: int = Field(1, ge=1, description="页码")
    size: int = Field(20, ge=1, le=100, description="每页大小")


class APIResponse(BaseModel):
    """通用API响应模型"""
    code: int = Field(..., description="响应码")
    message: str = Field(..., description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")


class HourlyAvailability(BaseModel):
    """每小时可用性模型"""
    hour: str = Field(..., description="时间 (HH:MM)")
    date: str = Field(..., description="日期 (YYYY-MM-DD)")
    datetime_display: str = Field(..., description="显示用时间 (MM/dd HH:MM)")
    is_occupied: bool = Field(..., description="是否被占用")
    can_start: bool = Field(..., description="是否可作为开始时间")
    status_color: str = Field(..., description="状态颜色: green/yellow/red")
    booking_id: Optional[int] = Field(None, description="占用的预订ID")


class RoomAvailabilityResponse(BaseModel):
    """包间可用性响应模型"""
    room_id: int
    room_name: str
    availability_hours: List[HourlyAvailability] = Field(..., description="72小时的可用性数据")
    existing_bookings: List[dict] = Field(..., description="现有预订记录")
    
    class Config:
        from_attributes = True


class RoomAvailabilityParams(BaseModel):
    """包间可用性查询参数"""
    room_id: int = Field(..., description="包间ID")
    start_date: Optional[str] = Field(None, description="开始日期 (YYYY-MM-DD)，默认今天")
    days: int = Field(default=3, ge=1, le=7, description="查询天数，默认3天")


class ReviewListResponse(BaseModel):
    """评价列表响应模型"""
    reviews: List[ReviewResponse]
    total: int
    page: int
    size: int
    pages: int


# ==================== 支付相关模型 ====================

class PaymentStatusEnum(str, Enum):
    """支付状态枚举"""
    PENDING = "pending"          # 待支付
    SUCCESS = "success"          # 支付成功
    FAILED = "failed"            # 支付失败
    REFUNDED = "refunded"        # 已退款
    CANCELLED = "cancelled"      # 已取消


class GetOpenidRequest(BaseModel):
    """获取openid请求模型"""
    code: str = Field(..., min_length=1, description="微信登录code")


class GetOpenidResponse(BaseModel):
    """获取openid响应模型"""
    errcode: int = Field(default=0, description="错误码")
    openid: Optional[str] = Field(None, description="微信openid")
    errmsg: Optional[str] = Field(None, description="错误信息")


class UnifiedOrderRequest(BaseModel):
    """统一下单请求模型"""
    openid: str = Field(..., description="用户openid")
    body: str = Field(..., min_length=1, max_length=128, description="商品描述")
    out_trade_no: str = Field(..., min_length=1, max_length=32, description="商户订单号")
    total_fee: int = Field(..., gt=0, description="总金额（分）")
    booking_id: Optional[int] = Field(None, description="关联预订ID，用于更新booking的payment_order_id")
    
    @validator('out_trade_no')
    def validate_out_trade_no(cls, v):
        """验证订单号格式"""
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('订单号只能包含字母、数字、下划线和横线')
        return v


class PaymentInfo(BaseModel):
    """支付参数模型"""
    timeStamp: str = Field(..., description="时间戳")
    nonceStr: str = Field(..., description="随机字符串")
    package: str = Field(..., description="统一下单接口返回的prepay_id参数值")
    signType: str = Field(default="MD5", description="签名类型")
    paySign: str = Field(..., description="签名")


class UnifiedOrderResponse(BaseModel):
    """统一下单响应模型"""
    errcode: int = Field(default=0, description="错误码")
    errmsg: Optional[str] = Field(None, description="错误信息")
    payment: Optional[PaymentInfo] = Field(None, description="支付参数")


class PaymentCallbackRequest(BaseModel):
    """支付回调请求模型"""
    return_code: str = Field(..., description="返回状态码")
    result_code: str = Field(..., description="业务结果")
    out_trade_no: str = Field(..., description="商户订单号")
    transaction_id: Optional[str] = Field(None, description="微信支付订单号")
    total_fee: Optional[int] = Field(None, description="总金额")
    openid: Optional[str] = Field(None, description="用户openid")
    time_end: Optional[str] = Field(None, description="支付完成时间")
    

class PaymentCallbackResponse(BaseModel):
    """支付回调响应模型"""
    errcode: int = Field(default=0, description="错误码")
    errmsg: str = Field(default="OK", description="返回信息")


class PaymentOrderCreate(BaseModel):
    """创建支付订单模型"""
    user_id: int = Field(..., description="用户ID")
    openid: str = Field(..., description="用户openid")
    out_trade_no: str = Field(..., description="商户订单号")
    body: str = Field(..., description="商品描述")
    total_fee: int = Field(..., description="总金额（分）")
    status: PaymentStatusEnum = Field(default=PaymentStatusEnum.PENDING, description="支付状态")
    transaction_id: Optional[str] = Field(None, description="微信支付订单号")
    ip_address: Optional[str] = Field(None, description="客户端IP")


class PaymentOrderResponse(BaseModel):
    """支付订单响应模型"""
    id: int
    user_id: int
    openid: str
    out_trade_no: str
    body: str
    total_fee: int
    status: PaymentStatusEnum
    transaction_id: Optional[str]
    created_at: str
    updated_at: str
    paid_at: Optional[str]
    
    @validator('created_at', 'updated_at', 'paid_at', pre=True)
    def convert_datetime_to_iso(cls, v):
        """将datetime对象转换为ISO格式字符串"""
        if isinstance(v, datetime):
            return v.isoformat()
        return v
    
    class Config:
        from_attributes = True


class PaymentOrderListResponse(BaseModel):
    """支付订单列表响应模型"""
    orders: List[PaymentOrderResponse]
    total: int
    page: int
    size: int
    pages: int


class PaymentOrderFilterParams(BaseModel):
    """支付订单过滤参数模型"""
    status: Optional[PaymentStatusEnum] = Field(None, description="支付状态")
    out_trade_no: Optional[str] = Field(None, description="商户订单号")
    transaction_id: Optional[str] = Field(None, description="微信支付订单号")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")


class WechatLoginRequest(BaseModel):
    """微信登录请求模型"""
    code: str = Field(..., description="微信登录code")
    user_info: WechatUserInfo = Field(...,
                                      description="微信用户信息",
                                      alias="userInfo")  # 添加别名匹配前端字段

    class Config:
        populate_by_name = True  # 启用别名支持


class Token(BaseModel):
    """JWT令牌模型"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class TokenData(BaseModel):
    """令牌数据模型"""
    user_id: Optional[int] = None
    openid: Optional[str] = None


class AuditLogCreate(BaseModel):
    """创建审计日志模型"""
    action: str = Field(..., min_length=1, max_length=50, description="操作类型")
    resource_type: Optional[str] = Field(None, max_length=50, description="资源类型")
    resource_id: Optional[str] = Field(None, max_length=50, description="资源ID")
    old_value: Optional[str] = Field(None, description="旧值")
    new_value: Optional[str] = Field(None, description="新值")
    ip_address: Optional[str] = Field(None, max_length=45, description="IP地址")
    user_agent: Optional[str] = Field(None, max_length=255, description="用户代理")
    description: Optional[str] = Field(None, description="操作描述")


class AuditLogResponse(BaseModel):
    """审计日志响应模型"""
    id: int
    user_id: int
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    old_value: Optional[str]
    new_value: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    description: Optional[str]
    created_at: str

    @validator('created_at', pre=True)
    def convert_datetime_to_iso(cls, v):
        """将datetime对象转换为ISO格式字符串"""
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """审计日志列表响应模型"""
    logs: List[AuditLogResponse]
    total: int
    page: int
    size: int
    pages: int


class UserFilterParams(BaseModel):
    """用户过滤参数模型"""
    nickname: Optional[str] = Field(None, description="昵称模糊查询")
    phone: Optional[str] = Field(None, description="手机号精确查询")
    email: Optional[str] = Field(None, description="邮箱精确查询")
    is_active: Optional[bool] = Field(None, description="是否激活")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")


class AuditLogFilterParams(BaseModel):
    """审计日志过滤参数模型"""
    action: Optional[str] = Field(None, description="操作类型")
    resource_type: Optional[str] = Field(None, description="资源类型")
    user_id: Optional[int] = Field(None, description="用户ID")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")


class UploadResponse(BaseModel):
    """文件上传响应模型"""
    file_url: str
    file_name: str
    file_size: int
    content_type: str


class WechatHeaders(BaseModel):
    """微信云托管请求头模型"""
    x_wx_openid: str = Field(..., alias="X-WX-OPENID", description="小程序用户openid")
    x_wx_appid: str = Field(..., alias="X-WX-APPID", description="小程序AppID")
    x_wx_unionid: Optional[str] = Field(None, alias="X-WX-UNIONID", description="小程序用户unionid")
    x_wx_from_openid: Optional[str] = Field(None, alias="X-WX-FROM-OPENID", description="资源复用情况下，小程序用户openid")
    x_wx_from_appid: Optional[str] = Field(None, alias="X-WX-FROM-APPID", description="资源复用情况下，使用方小程序AppID")
    x_wx_from_unionid: Optional[str] = Field(None, alias="X-WX-FROM-UNIONID", description="资源复用情况下，小程序用户unionid")
    x_wx_env: Optional[str] = Field(None, alias="X-WX-ENV", description="所在云环境ID")
    x_wx_source: Optional[str] = Field(None, alias="X-WX-SOURCE", description="调用来源")
    x_forwarded_for: Optional[str] = Field(None, alias="X-Forwarded-For", description="客户端IP地址")

    class Config:
        populate_by_name = True
class BookingUpdate(BaseModel):
    """更新预订模型"""
    remark: Optional[str] = Field(None, max_length=500, description="备注信息")
class DoorOpenRequest(BaseModel):
    """开门请求模型"""
    door_id: int = Field(..., ge=1, description="门ID")


class DoorOpenResponse(BaseModel):
    """开门响应模型"""
    relay_id: int = Field(..., description="继电器ID")
    status: str = Field(..., description="状态")