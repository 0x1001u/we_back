import os
import uuid
import aiofiles
from fastapi import UploadFile, HTTPException, status
from typing import Optional
from PIL import Image
from io import BytesIO
import hashlib
from app.config import settings


class FileUploadService:
    """文件上传服务"""
    
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        self.max_size = settings.MAX_UPLOAD_SIZE
        self.allowed_types = settings.ALLOWED_IMAGE_TYPES
        self._ensure_upload_dir()
    
    def _ensure_upload_dir(self):
        """确保上传目录存在"""
        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir, exist_ok=True)
    
    def _generate_filename(self, original_filename: str, prefix: str = "avatar") -> str:
        """生成唯一文件名"""
        ext = original_filename.split('.')[-1] if '.' in original_filename else ''
        unique_id = str(uuid.uuid4())
        timestamp = str(int(os.path.getmtime(__file__)))
        hash_input = f"{unique_id}{timestamp}{original_filename}"
        file_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        
        if ext:
            return f"{prefix}_{file_hash}_{unique_id[:8]}.{ext}"
        else:
            return f"{prefix}_{file_hash}_{unique_id[:8]}"
    
    def _validate_file(self, file: UploadFile) -> bool:
        """验证文件"""
        # 检查文件类型
        if file.content_type not in self.allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type {file.content_type} not allowed. Allowed types: {self.allowed_types}"
            )
        
        # 检查文件大小
        if file.size and file.size > self.max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size {file.size} exceeds maximum allowed size {self.max_size}"
            )
        
        return True
    
    async def _save_file(self, file: UploadFile, filename: str) -> str:
        """保存文件"""
        file_path = os.path.join(self.upload_dir, filename)
        
        try:
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
            
            return file_path
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save file: {str(e)}"
            )
    
    def _optimize_image(self, file_path: str, max_size: tuple = (800, 800)) -> str:
        """优化图片"""
        try:
            with Image.open(file_path) as img:
                # 转换为RGB模式（处理PNG的透明背景）
                if img.mode in ('RGBA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'RGBA':
                        background.paste(img, mask=img.split()[3])
                    else:
                        background.paste(img)
                    img = background
                
                # 调整大小
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # 保存优化后的图片
                img.save(file_path, optimize=True, quality=85)
                
            return file_path
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to optimize image: {str(e)}"
            )
    
    async def upload_avatar(self, file: UploadFile, user_id: Optional[int] = None) -> dict:
        """上传头像"""
        # 验证文件
        self._validate_file(file)
        
        # 生成文件名
        prefix = f"user_{user_id}" if user_id else "avatar"
        filename = self._generate_filename(file.filename or "avatar.jpg", prefix)
        
        # 保存文件
        file_path = await self._save_file(file, filename)
        
        # 优化图片
        self._optimize_image(file_path)
        
        # 获取文件信息
        file_size = os.path.getsize(file_path)
        
        # 构建文件URL
        file_url = f"/{self.upload_dir}/{filename}"
        
        return {
            "file_url": file_url,
            "file_name": filename,
            "file_size": file_size,
            "content_type": file.content_type
        }
    
    async def delete_file(self, file_url: str) -> bool:
        """删除文件"""
        try:
            # 从URL中提取文件名
            filename = file_url.split('/')[-1]
            file_path = os.path.join(self.upload_dir, filename)
            
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            
            return False
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete file: {str(e)}"
            )
    
    def get_file_info(self, file_url: str) -> dict:
        """获取文件信息"""
        try:
            # 从URL中提取文件名
            filename = file_url.split('/')[-1]
            file_path = os.path.join(self.upload_dir, filename)
            
            if not os.path.exists(file_path):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found"
                )
            
            file_size = os.path.getsize(file_path)
            
            # 简单的内容类型判断
            ext = filename.split('.')[-1].lower()
            content_type = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'gif': 'image/gif'
            }.get(ext, 'application/octet-stream')
            
            return {
                "file_url": file_url,
                "file_name": filename,
                "file_size": file_size,
                "content_type": content_type,
                "exists": True
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get file info: {str(e)}"
            )


# 创建文件上传服务实例
file_upload_service = FileUploadService()