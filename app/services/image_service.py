"""
真实图片生成服务模块
使用火山引擎方舟 Doubao 图片生成 API
"""
import os
import asyncio
from typing import List

from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量
load_dotenv()


class ImageService:
    """图片生成服务类 - 使用 Doubao Image API"""

    def __init__(self):
        # 这里默认复用与文本 LLM 相同的 Key / Base URL
        # 如需单独配置，可新增 IMAGE_API_KEY / IMAGE_BASE_URL 环境变量
        self.api_key = os.getenv("IMAGE_API_KEY") or os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv(
            "IMAGE_BASE_URL",
            os.getenv("LLM_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
        )
        # 默认图片模型，可通过环境变量覆盖
        self.model = os.getenv("IMAGE_MODEL", "doubao-seedream-4-5-251128")

        if not self.api_key:
            raise ValueError("IMAGE_API_KEY / LLM_API_KEY 未配置，无法调用图片生成 API")

        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        """懒加载 OpenAI 客户端"""
        if self._client is None:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    def _generate_single_image_sync(
        self,
        prompt: str,
        size: str = "2k",
    ) -> str:
        """
        同步调用方舟图片生成接口，返回单张图片 URL
        """
        images_response = self.client.images.generate(
            model=self.model,
            prompt=prompt,
            size=size,
            response_format="url",
        )

        if not images_response.data:
            raise RuntimeError("图片生成接口返回为空")

        return images_response.data[0].url

    async def generate_single_image(
        self,
        prompt: str,
        size: str = "2k",
    ) -> str:
        """
        生成单张图片（异步封装）

        Args:
            prompt: 图片描述文案
            size: 图片尺寸

        Returns:
            图片 URL
        """
        # Ark 当前使用字符串形式的 size，这里用 "宽x高" 形式
        loop = asyncio.get_running_loop()
        url = await loop.run_in_executor(
            None,
            self._generate_single_image_sync,
            prompt,
            size,
        )
        return url

    async def generate_images(
        self,
        visual_points: List[str],
        size: str = "2k",
    ) -> List[str]:
        """
        根据视觉要点批量生成配图（串行调用，保持接口简单）

        Args:
            visual_points: 文案要点列表
            size: 图片尺寸

        Returns:
            图片 URL 列表
        """
        if not visual_points:
            return []

        image_urls: List[str] = []
        for point in visual_points:
            url = await self.generate_single_image(
                prompt=point,
                size=size,
            )
            image_urls.append(url)

        return image_urls


# 创建单例实例，供 get_image_service 使用
image_service = ImageService()

