"""POI相关API路由"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from ...runtime.factory import AppRuntime, get_app_runtime

router = APIRouter(prefix="/poi", tags=["POI"])


class POIDetailResponse(BaseModel):
    """POI详情响应"""
    success: bool
    message: str
    data: Optional[dict] = None


class AttractionPhotoResponse(BaseModel):
    """景点图片响应：命中返回真实图片；未命中/失败返回中性占位语义（HTTP 200）。

    前端据此渲染真实图片或"示意图"占位，不再出现与目的地不符的城市照片。
    """

    name: str = Field(..., description="景点名称")
    success: bool = Field(..., description="请求是否成功")
    message: str = Field(default="", description="消息")
    photo_url: Optional[str] = Field(default=None, description="真实图片URL；无匹配时为 null")
    is_placeholder: bool = Field(default=False, description="是否为中性占位图（无真实图片）")
    warnings: List[str] = Field(default_factory=list, description="降级/失败告警清单")
    data: Optional[dict] = Field(default=None, description="兼容旧契约的 {name, photo_url} 载荷")


@router.get(
    "/detail/{poi_id}",
    response_model=POIDetailResponse,
    summary="获取POI详情",
    description="根据POI ID获取详细信息,包括图片"
)
async def get_poi_detail(
    poi_id: str,
    runtime: AppRuntime = Depends(get_app_runtime),
):
    """
    获取POI详情
    
    Args:
        poi_id: POI ID
        
    Returns:
        POI详情响应
    """
    try:
        amap_service = runtime.factory.create_amap_service()
        
        # 调用高德地图POI详情API
        result = amap_service.get_poi_detail(poi_id)
        
        return POIDetailResponse(
            success=True,
            message="获取POI详情成功",
            data=result
        )
        
    except Exception as e:
        print(f"❌ 获取POI详情失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取POI详情失败: {str(e)}"
        )


@router.get(
    "/search",
    summary="搜索POI",
    description="根据关键词搜索POI"
)
async def search_poi(
    keywords: str,
    city: str = "北京",
    runtime: AppRuntime = Depends(get_app_runtime),
):
    """
    搜索POI

    Args:
        keywords: 搜索关键词
        city: 城市名称

    Returns:
        搜索结果
    """
    try:
        amap_service = runtime.factory.create_amap_service()
        result = amap_service.search_poi(keywords, city)

        return {
            "success": True,
            "message": "搜索成功",
            "data": result
        }

    except Exception as e:
        print(f"❌ 搜索POI失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"搜索POI失败: {str(e)}"
        )


@router.get(
    "/photo",
    response_model=AttractionPhotoResponse,
    summary="获取景点图片",
    description="根据景点名称从Unsplash获取图片；未命中或服务失败返回中性占位语义"
)
async def get_attraction_photo(
    name: str,
    runtime: AppRuntime = Depends(get_app_runtime),
):
    """返回真实图片；未命中/异常均以 HTTP 200 返回中性占位语义。"""
    try:
        unsplash_service = runtime.factory.create_unsplash()
        photo_url = unsplash_service.get_photo_url(f"{name} China landmark")
        if photo_url:
            return AttractionPhotoResponse(
                name=name,
                success=True,
                message="获取图片成功",
                photo_url=photo_url,
                is_placeholder=False,
                warnings=[],
                data={"name": name, "photo_url": photo_url},
            )
        return AttractionPhotoResponse(
            name=name,
            success=True,
            message="未找到匹配图片，使用中性占位图",
            photo_url=None,
            is_placeholder=True,
            warnings=[f"未找到与景点'{name}'匹配的图片"],
            data={"name": name, "photo_url": None},
        )
    except Exception as e:
        warning = f"获取景点图片失败: {e}"
        return AttractionPhotoResponse(
            name=name,
            success=False,
            message=warning,
            photo_url=None,
            is_placeholder=True,
            warnings=[warning],
            data={"name": name, "photo_url": None},
        )

