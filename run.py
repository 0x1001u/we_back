import uvicorn
import sys
import os
import logging

# 添加app目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info(f"🚀 启动棋牌室预订系统后端服务...")
    logger.info(f"📍 环境: {settings.NODE_ENV}")
    logger.info(f"🔗 端口: {settings.PORT}")
    logger.info(f"☁️ 云托管模式: {settings.USE_CLOUD}")
    
    try:
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=settings.PORT,
            reload=settings.NODE_ENV == "development",
            log_level="info",
            access_log=True
        )
    except Exception as e:
        logger.error(f"❌ 服务启动失败: {str(e)}")
        sys.exit(1)