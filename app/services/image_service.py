"""
图片生成服务模块
使用 Gemini 3 Pro Image Preview 模型生成小红书爆款配图
"""
import os
import re
import asyncio
import base64
import uuid
import httpx
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class ImageService:
    """图片生成服务类 - 使用 Gemini Image API"""

    # 小红书爆款图片提示词模板
    XHS_STYLE_PROMPT = """
请根据以下内容生成一张小红书风格的爆款配图：

【内容主题】
{content}

【图片要求】
- 风格：小红书流行的高质感、精致感、氛围感风格
- 色调：明亮温暖、柔和治愈、或高级感色调
- 构图：简洁大气、留白得当、视觉重点突出
- 细节：画面精致、质感细腻、光影自然
- 比例：3:4 竖版构图（适合手机浏览）
- 氛围：营造出让人想点赞收藏的吸引力

【风格参考】
- 如果是美食：诱人的食物特写，暖色调打光，精致摆盘
- 如果是穿搭：时尚感穿搭展示，简约背景，模特姿态自然
- 如果是家居：温馨舒适的生活场景，ins风或日系风
- 如果是旅行：唯美风景或打卡场景，色彩鲜艳
- 如果是知识/干货：清新简约的图文排版风格，扁平插画
- 如果是美妆护肤：产品精致展示，柔光效果
- 其他：根据内容匹配最适合的小红书流行风格

请生成一张高质量、有吸引力的图片，让人看到就想点击。
"""

    def __init__(self):
        self.api_key = os.getenv("IMAGE_API_KEY", "")
        self.base_url = os.getenv("IMAGE_BASE_URL", "https://cn-beijing.yuannengai.com")
        self.model = os.getenv("IMAGE_MODEL", "gemini-3-pro-image-preview")
        
        # 图片保存目录
        self.image_dir = Path("static/images/generated")
        self.image_dir.mkdir(parents=True, exist_ok=True)

        if not self.api_key:
            raise ValueError("IMAGE_API_KEY 未配置，无法调用图片生成 API")

    def _build_api_url(self) -> str:
        """构建 API URL"""
        return f"{self.base_url}/v1beta/models/{self.model}:generateContent"

    def _optimize_prompt_for_xhs(self, content: str) -> str:
        """
        优化提示词，生成小红书爆款风格图片
        
        Args:
            content: 原始内容描述
            
        Returns:
            优化后的提示词
        """
        return self.XHS_STYLE_PROMPT.format(content=content)

    def _sanitize_prompt(self, prompt: str) -> str:
        """
        净化提示词，移除可能触发敏感检测的内容
        
        Args:
            prompt: 原始提示词
            
        Returns:
            净化后的提示词
        """
        sensitive_patterns = [
            r'[政治|军事|暴力|血腥|恐怖|色情|裸体|赌博|毒品]',
            r'[领导人|主席|总统|政府|党]',
            r'[战争|武器|枪|刀|炸弹]',
        ]
        
        result = prompt
        for pattern in sensitive_patterns:
            result = re.sub(pattern, '', result)
        
        return result.strip()

    def _create_fallback_prompt(self, original_prompt: str) -> str:
        """
        创建备用的通用提示词
        
        Args:
            original_prompt: 原始提示词
            
        Returns:
            更安全的备用提示词
        """
        style_keywords = []
        if '插画' in original_prompt:
            style_keywords.append('插画风格')
        if '扁平' in original_prompt:
            style_keywords.append('扁平化设计')
        if '现代' in original_prompt:
            style_keywords.append('现代简约')
        if '温馨' in original_prompt or '治愈' in original_prompt:
            style_keywords.append('温馨治愈')
        
        if not style_keywords:
            style_keywords = ['小红书风格', '简约精致']
        
        import random
        fallback_prompts = [
            f"{', '.join(style_keywords)}，明亮温暖的生活场景，咖啡和书本，柔和自然光，3:4竖版构图",
            f"{', '.join(style_keywords)}，创意工作台，文具和绿植，ins风格，3:4竖版构图",
            f"{', '.join(style_keywords)}，清新简约的扁平插画，渐变色背景，3:4竖版构图",
        ]
        
        return random.choice(fallback_prompts)

    def _save_image(self, image_base64: str, prefix: str = "xhs") -> str:
        """
        保存 base64 图片到本地
        
        Args:
            image_base64: base64 编码的图片数据
            prefix: 文件名前缀
            
        Returns:
            图片的相对路径（用于访问）
        """
        # 生成唯一文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{prefix}_{timestamp}_{unique_id}.png"
        
        # 保存文件
        file_path = self.image_dir / filename
        with open(file_path, "wb") as f:
            f.write(base64.b64decode(image_base64))
        
        # 返回可访问的相对路径
        return f"/static/images/generated/{filename}"

    async def _call_gemini_api(self, prompt: str) -> Optional[str]:
        """
        调用 Gemini 图片生成 API
        
        Args:
            prompt: 图片描述提示词
            
        Returns:
            base64 编码的图片数据，失败返回 None
        """
        url = self._build_api_url()
        
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "responseModalities": ["IMAGE", "TEXT"]
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                
                # 提取图像数据
                if "candidates" in result and result["candidates"]:
                    for part in result["candidates"][0]["content"]["parts"]:
                        if "inlineData" in part:
                            return part["inlineData"]["data"]
                
                print(f"[ImageService] API 响应中未找到图片数据: {result}")
                return None
                
        except httpx.HTTPStatusError as e:
            print(f"[ImageService] HTTP 错误: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            print(f"[ImageService] 请求异常: {e}")
            return None

    async def generate_single_image(
        self,
        prompt: str,
        optimize_for_xhs: bool = True,
    ) -> Optional[str]:
        """
        生成单张图片
        
        Args:
            prompt: 图片描述文案
            optimize_for_xhs: 是否优化为小红书风格（默认开启）
            
        Returns:
            图片访问路径，如果生成失败则返回 None
        """
        max_retries = 2
        
        # 优化提示词
        if optimize_for_xhs:
            current_prompt = self._optimize_prompt_for_xhs(prompt)
        else:
            current_prompt = prompt
        
        for attempt in range(max_retries + 1):
            print(f"[ImageService] 生成图片 (尝试 {attempt + 1}): {prompt[:50]}...")
            
            image_base64 = await self._call_gemini_api(current_prompt)
            
            if image_base64:
                # 保存图片并返回路径
                image_path = self._save_image(image_base64)
                print(f"[ImageService] 图片生成成功: {image_path}")
                return image_path
            
            # 重试策略
            if attempt == 0:
                # 第一次重试：净化提示词
                current_prompt = self._sanitize_prompt(current_prompt)
                print(f"[ImageService] 净化提示词后重试...")
            elif attempt == 1:
                # 第二次重试：使用备用提示词
                current_prompt = self._create_fallback_prompt(prompt)
                print(f"[ImageService] 使用备用提示词重试...")
            
            # 等待一下再重试
            await asyncio.sleep(1)
        
        print(f"[ImageService] 图片生成失败，跳过: {prompt[:50]}...")
        return None

    async def generate_images(
        self,
        visual_points: List[str],
        optimize_for_xhs: bool = True,
    ) -> List[str]:
        """
        根据视觉要点批量生成配图（并行调用，带错误处理）
        
        Args:
            visual_points: 文案要点列表
            optimize_for_xhs: 是否优化为小红书风格
            
        Returns:
            图片路径列表（失败的会被过滤掉）
        """
        if not visual_points:
            return []

        # 并行生成所有图片
        tasks = [
            self.generate_single_image(prompt=point, optimize_for_xhs=optimize_for_xhs)
            for point in visual_points
        ]
        results = await asyncio.gather(*tasks)

        # 过滤掉失败的（None）
        image_paths = [path for path in results if path is not None]
        
        print(f"[ImageService] 成功生成 {len(image_paths)}/{len(visual_points)} 张图片")
        return image_paths


# 创建单例实例，供 get_image_service 使用
image_service = ImageService()
