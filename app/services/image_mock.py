"""
Mock 图片生成服务模块
模拟图片生成 API 调用，用于开发和测试
"""
import asyncio
from typing import List, Tuple
import hashlib


class MockImageService:
    """Mock 图片生成服务类"""
    
    # 占位图片服务基础 URL
    PLACEHOLDER_BASE_URL = "https://via.placeholder.com"
    
    # 模拟模型名称，用于调试
    model = "mock-image-model"
    
    # size 字符串到像素尺寸的映射
    SIZE_MAPPING = {
        "2k": (2048, 1536),
        "1080p": (1920, 1080),
        "720p": (1280, 720),
        "square": (1080, 1080),
        "portrait": (1080, 1920),
        "landscape": (1920, 1080),
    }
    
    @staticmethod
    def _parse_size(size: str) -> Tuple[int, int]:
        """
        解析 size 字符串为宽高像素值
        
        支持格式:
        - 预设值: "2k", "1080p", "720p", "square", "portrait", "landscape"
        - 自定义: "宽x高" 如 "800x600"
        
        Args:
            size: 尺寸字符串
            
        Returns:
            (width, height) 元组
        """
        # 先检查预设值
        if size.lower() in MockImageService.SIZE_MAPPING:
            return MockImageService.SIZE_MAPPING[size.lower()]
        
        # 尝试解析 "宽x高" 格式
        if "x" in size.lower():
            try:
                parts = size.lower().split("x")
                return int(parts[0]), int(parts[1])
            except (ValueError, IndexError):
                pass
        
        # 默认返回 2k 尺寸
        return (2048, 1536)
    
    @staticmethod
    async def generate_images(
        visual_points: List[str],
        size: str = "2k",
    ) -> List[str]:
        """
        根据视觉要点生成配图
        
        Args:
            visual_points: 图片文案要点列表
            size: 图片尺寸，支持 "2k", "1080p", "720p", "square", "portrait", "landscape" 或 "宽x高"
            
        Returns:
            生成的图片 URL 列表
        """
        # 模拟 API 延迟
        await asyncio.sleep(0.8)
        
        image_urls = []
        colors = ["3498db", "e74c3c", "2ecc71", "9b59b6", "f39c12"]
        
        # 解析尺寸
        width, height = MockImageService._parse_size(size)
        size_str = f"{width}x{height}"
        
        for i, point in enumerate(visual_points):
            # 生成唯一的图片标识
            hash_id = hashlib.md5(point.encode()).hexdigest()[:8]
            color = colors[i % len(colors)]
            
            # 生成占位图片 URL
            # 格式: https://via.placeholder.com/{size}/{color}/ffffff?text={text}
            text = f"Image_{i+1}_{hash_id}"
            url = f"{MockImageService.PLACEHOLDER_BASE_URL}/{size_str}/{color}/ffffff?text={text}"
            
            image_urls.append(url)
        
        return image_urls
    
    @staticmethod
    async def generate_single_image(
        prompt: str,
        size: str = "2k",
    ) -> str:
        """
        生成单张图片
        
        Args:
            prompt: 图片描述
            size: 图片尺寸，支持 "2k", "1080p", "720p", "square", "portrait", "landscape" 或 "宽x高"
            
        Returns:
            生成的图片 URL
        """
        # 模拟 API 延迟
        await asyncio.sleep(0.5)
        
        # 解析尺寸
        width, height = MockImageService._parse_size(size)
        
        hash_id = hashlib.md5(prompt.encode()).hexdigest()[:8]
        url = f"{MockImageService.PLACEHOLDER_BASE_URL}/{width}x{height}/3498db/ffffff?text={hash_id}"
        
        return url


# 创建单例实例
mock_image_service = MockImageService()
