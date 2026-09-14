"""Unsplash图片服务：依赖注入构造，无进程级单例。"""

import requests
from typing import List, Optional
from ..config import get_settings, Settings

class UnsplashService:
    """Unsplash图片服务类"""
    
    def __init__(self, access_key: Optional[str] = None):
        """初始化服务：access_key 可由调用方注入（测试桩）或从 Settings 读取。"""
        settings = get_settings()
        self.access_key = access_key if access_key is not None else settings.unsplash_access_key
        self.base_url = "https://api.unsplash.com"
    
    def search_photos(self, query: str, per_page: int = 5) -> List[dict]:
        """
        搜索图片
        
        Args:
            query: 搜索关键词
            per_page: 每页数量
            
        Returns:
            图片列表
        """
        try:
            url = f"{self.base_url}/search/photos"
            params = {
                "query": query,
                "per_page": per_page,
                "client_id": self.access_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = data.get("results", [])
            
            # 提取图片URL
            photos = []
            for photo in results:
                photos.append({
                    "id": photo.get("id"),
                    "url": photo.get("urls", {}).get("regular"),
                    "thumb": photo.get("urls", {}).get("thumb"),
                    "description": photo.get("description") or photo.get("alt_description"),
                    "photographer": photo.get("user", {}).get("name")
                })
            
            return photos
            
        except Exception as e:
            print(f"❌ Unsplash搜索失败: {str(e)}")
            return []
    
    def get_photo_url(self, query: str) -> Optional[str]:
        """
        获取单张图片URL

        Args:
            query: 搜索关键词

        Returns:
            图片URL
        """
        photos = self.search_photos(query, per_page=1)
        if photos:
            return photos[0].get("url")
        return None


def create_unsplash(settings: Optional[Settings] = None) -> UnsplashService:
    """构造 Unsplash 服务实例（每次调用返回独立实例，便于按需注入或替换为测试桩）。"""
    s = settings if settings is not None else get_settings()
    return UnsplashService(access_key=s.unsplash_access_key)

