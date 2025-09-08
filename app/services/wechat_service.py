import httpx
import json
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from app.config import settings


class WechatService:
    """微信服务类，处理微信API调用"""
    
    def __init__(self):
        self.app_id = settings.WECHAT_APP_ID
        self.app_secret = settings.WECHAT_APP_SECRET
        self.disable_ssl_validation = settings.DISABLE_WECHAT_SSL_VALIDATION
    
    async def get_openid_by_code(self, code: str) -> Dict[str, Any]:
        """
        通过微信登录code获取openid和session_key
        
        Args:
            code: 微信登录code
            
        Returns:
            Dict包含openid, session_key, unionid(可选)
            
        Raises:
            HTTPException: 当微信API调用失败时
        """
        try:
            # 微信API URL
            url = "https://api.weixin.qq.com/sns/jscode2session"
            
            # 请求参数
            params = {
                "appid": self.app_id,
                "secret": self.app_secret,
                "js_code": code,
                "grant_type": "authorization_code"
            }
            
            # 配置HTTP客户端
            verify_ssl = not self.disable_ssl_validation
            timeout = httpx.Timeout(10.0)  # 10秒超时
            
            async with httpx.AsyncClient(verify=verify_ssl, timeout=timeout) as client:
                response = await client.get(url, params=params)
                
                # 检查响应状态
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"WeChat API request failed: {response.status_code}"
                    )
                
                # 解析响应数据
                data = response.json()
                
                # 检查微信API返回的错误
                if "errcode" in data and data["errcode"] != 0:
                    error_msg = data.get("errmsg", "Unknown WeChat API error")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"WeChat API error: {error_msg}"
                    )
                
                # 验证必要字段
                if "openid" not in data:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="WeChat API response missing openid"
                    )
                
                return {
                    "openid": data["openid"],
                    "session_key": data.get("session_key", ""),
                    "unionid": data.get("unionid")  # unionid可能不存在
                }
                
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="WeChat API request timeout"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"WeChat API request error: {str(e)}"
            )
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid JSON response from WeChat API"
            )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error calling WeChat API: {str(e)}"
            )
    
    def validate_wechat_signature(self, signature: str, timestamp: str, nonce: str, token: str) -> bool:
        """
        验证微信服务器签名（用于服务器配置验证）
        
        Args:
            signature: 微信服务器签名
            timestamp: 时间戳
            nonce: 随机数
            token: 开发者设置的token
            
        Returns:
            bool: 签名是否有效
        """
        try:
            import hashlib
            
            # 按字典序排序参数
            params = [token, timestamp, nonce]
            params.sort()
            
            # 拼接字符串并SHA1加密
            temp_str = "".join(params)
            sha1 = hashlib.sha1()
            sha1.update(temp_str.encode('utf-8'))
            hash_code = sha1.hexdigest()
            
            # 对比签名
            return hash_code == signature
        except Exception:
            return False
    
    async def get_wechat_user_info(self, access_token: str, openid: str) -> Dict[str, Any]:
        """
        通过access_token获取微信用户详细信息（需要用户授权）
        
        Args:
            access_token: 微信access_token
            openid: 用户openid
            
        Returns:
            Dict包含用户详细信息
        """
        try:
            url = "https://api.weixin.qq.com/sns/userinfo"
            
            params = {
                "access_token": access_token,
                "openid": openid,
                "lang": "zh_CN"
            }
            
            verify_ssl = not self.disable_ssl_validation
            timeout = httpx.Timeout(10.0)
            
            async with httpx.AsyncClient(verify=verify_ssl, timeout=timeout) as client:
                response = await client.get(url, params=params)
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"WeChat user info request failed: {response.status_code}"
                    )
                
                data = response.json()
                
                if "errcode" in data and data["errcode"] != 0:
                    error_msg = data.get("errmsg", "Unknown WeChat API error")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"WeChat user info error: {error_msg}"
                    )
                
                return data
                
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error getting WeChat user info: {str(e)}"
            )