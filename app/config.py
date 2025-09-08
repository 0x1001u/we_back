import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """应用配置类，自动从环境变量加载配置"""
    
    # 基础配置
    NODE_ENV: str = Field(default="production")
    PORT: int = Field(default=80)
    USE_CLOUD: bool = Field(default=True)
    
    # JWT配置 - 云托管环境必需
    JWT_SECRET: str = Field(default="cloud-default-jwt-secret-change-in-production", description="JWT密钥")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 120  # 2小时
    JWT_REFRESH_EXPIRE_MINUTES: int = 60 * 24 * 7  # refresh token 7天
    
    # 微信小程序配置 - 云托管环境自动注入
    WECHAT_APP_ID: str = Field(default="", description="微信小程序AppID")
    WECHAT_APP_SECRET: str = Field(default="", description="微信小程序AppSecret")
    
    # 微信支付配置
    WECHAT_MCH_ID: str = Field(default="")
    WECHAT_MCH_KEY: str = Field(default="")
    WECHAT_SUB_MCH_ID: str = Field(default="")
    WECHAT_SUB_MCH_KEY: str = Field(default="")
    
    # 云托管环境配置
    CLOUD_ENV_ID: str = Field(default="")
    
    # 数据库配置 - 云托管环境自动注入
    DB_HOST: str = Field(default="localhost")
    DB_PORT: int = Field(default=3306)
    DB_NAME: str = Field(default="wechat_miniprogram")
    DB_USER: str = Field(default="root")
    DB_PASSWORD: str = Field(default="")
    
    # 微信登录SSL验证
    DISABLE_WECHAT_SSL_VALIDATION: bool = Field(default=True)
    
    # 文件上传配置
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_IMAGE_TYPES: list[str] = ["image/jpeg", "image/png", "image/gif"]
    
    # 分页配置
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    @property
    def database_url(self) -> str:
        """构建数据库连接URL"""
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# 创建全局配置实例
settings = Settings()