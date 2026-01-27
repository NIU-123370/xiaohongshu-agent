"""
Mock 图片生成服务模块
模拟图片生成 API 调用，用于开发和测试
"""
import asyncio
from typing import List
import hashlib


class MockImageService:
    """Mock 图片生成服务类"""
    
    # 占位图片服务基础 URL
    PLACEHOLDER_BASE_URL = "https://via.placeholder.com"
    
    @staticmethod
    async def generate_images(visual_points: List[str]) -> List[str]:
        """
        根据视觉要点生成配图
        
        Args:
            visual_points: 图片文案要点列表
            
        Returns:
            生成的图片 URL 列表
        """
        # 模拟 API 延迟
        await asyncio.sleep(0.8)
        
        image_urls = []
        
        # 为每个视觉要点生成一个占位图片 URL
        sizes = ["800x600", "1200x630", "600x400", "1080x1080", "750x500"]
        colors = ["3498db", "e74c3c", "2ecc71", "9b59b6", "f39c12"]
        
        for i, point in enumerate(visual_points):
            # 生成唯一的图片标识
            hash_id = hashlib.md5(point.encode()).hexdigest()[:8]
            size = sizes[i % len(sizes)]
            color = colors[i % len(colors)]
            
            # 生成占位图片 URL
            # 格式: https://via.placeholder.com/{size}/{color}/ffffff?text={text}
            text = f"Image_{i+1}_{hash_id}"
            url = f"{MockImageService.PLACEHOLDER_BASE_URL}/{size}/{color}/ffffff?text={text}"
            
            image_urls.append(url)
        
        return image_urls
    
    @staticmethod
    async def generate_single_image(
        prompt: str, 
        width: int = 800, 
        height: int = 600
    ) -> str:
        """
        生成单张图片
        
        Args:
            prompt: 图片描述
            width: 图片宽度
            height: 图片高度
            
        Returns:
            生成的图片 URL
        """
        # 模拟 API 延迟
        await asyncio.sleep(0.5)
        
        hash_id = hashlib.md5(prompt.encode()).hexdigest()[:8]
        url = f"{MockImageService.PLACEHOLDER_BASE_URL}/{width}x{height}/3498db/ffffff?text={hash_id}"
        
        return url


# 创建单例实例
mock_image_service = MockImageService()
