from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.middleware.csrf import CSRFMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import uvicorn
import os
from app.config import settings
from app.routers import users, payment, rooms, bookings, reviews
from app.models.database import create_tables

# 创建FastAPI应用
app = FastAPI(
    title="微信小程序用户管理后端",
    description="基于FastAPI的微信小程序用户管理后端系统",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置CSRF保护
app.add_middleware(
    CSRFMiddleware,
    exempt_paths=[
        "/",
        "/health",
        "/api/v1/wechat-info",
        "/docs",
        "/redoc",
        "/api/users/auto-login"  # 自动登录接口豁免CSRF验证
    ]
)

# 静态文件服务
if os.path.exists(settings.UPLOAD_DIR):
    app.mount(f"/{settings.UPLOAD_DIR}", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# 添加路由
app.include_router(users.router, prefix="/api/v1")
app.include_router(payment.router, prefix="/api/v1")
app.include_router(rooms.router)
app.include_router(bookings.router)
app.include_router(reviews.router)

# 添加调试路由信息
@app.on_event("startup")
async def log_routes():
    """打印所有注册的路由"""
    print("=== 已注册的路由 ===")
    from fastapi.routing import APIRoute
    for route in app.routes:
        if isinstance(route, APIRoute):
            print(f"路径: {route.path}, 方法: {list(route.methods)}, 名称: {route.name}")
    print("==================")

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    try:
        # 创建数据库表
        create_tables()
        print("✅ 数据库表创建完成")
        
        # 初始化棋牌室示例数据（仅在表为空时执行）
        from app.models.database import init_room_sample_data
        init_room_sample_data()
        print("✅ 棋牌室示例数据初始化完成")
        
        print("🚀 应用启动成功，所有功能模块已就绪")
    except Exception as e:
        print(f"⚠️ 应用启动时出现错误: {str(e)}")
        # 不要抛出异常，让应用继续启动
        print("应用将继续启动，请检查数据库连接和配置")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    print("应用关闭")

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """HTTP异常处理器"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.detail,
            "data": None
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求验证异常处理器"""
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "请求参数验证失败",
            "data": {
                "errors": exc.errors()
            }
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理器"""
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "data": None
        }
    )

@app.get("/")
async def root():
    """根路径"""
    return {
        "code": 0,
        "message": "微信小程序用户管理后端API",
        "data": {
            "service": "xinghui",
            "version": "1.0.0",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "code": 0,
        "message": "success",
        "data": {
            "status": "healthy",
            "service": "xinghui",
            "environment": settings.NODE_ENV
        }
    }

@app.get("/api/v1/wechat-info")
async def get_wechat_info(request: Request):
    """获取微信云托管请求信息"""
    headers = dict(request.headers)
    wechat_headers = {
        "X-WX-OPENID": headers.get("X-WX-OPENID"),
        "X-WX-APPID": headers.get("X-WX-APPID"),
        "X-WX-UNIONID": headers.get("X-WX-UNIONID"),
        "X-WX-FROM-OPENID": headers.get("X-WX-FROM-OPENID"),
        "X-WX-FROM-APPID": headers.get("X-WX-FROM-APPID"),
        "X-WX-FROM-UNIONID": headers.get("X-WX-FROM-UNIONID"),
        "X-WX-ENV": headers.get("X-WX-ENV"),
        "X-WX-SOURCE": headers.get("X-WX-SOURCE"),
        "X-Forwarded-For": headers.get("X-Forwarded-For")
    }
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "wechat_headers": wechat_headers,
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": headers.get("User-Agent", "unknown")
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.NODE_ENV == "development",
        log_level="info"
    )