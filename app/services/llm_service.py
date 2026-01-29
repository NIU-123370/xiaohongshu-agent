"""
LLM 服务模块
使用火山引擎 Doubao API 进行 LLM 调用
"""
import os
from typing import List, Tuple, Optional
from dataclasses import dataclass
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# 加载环境变量
load_dotenv()


@dataclass
class LLMUsageInfo:
    """LLM 调用的 token 使用信息"""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model: str = ""


class LLMService:
    """LLM 服务类 - 使用火山引擎 Doubao API"""
    
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
        self.model = os.getenv("LLM_MODEL", "doubao-seed-1-8-251228")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0"))
        
        # 初始化 LLM 客户端
        self._llm = None
    
    @property
    def llm(self) -> ChatOpenAI:
        """懒加载 LLM 客户端"""
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._llm
    
    def _extract_usage_info(self, response) -> LLMUsageInfo:
        """从 LLM 响应中提取 token 使用信息"""
        usage = LLMUsageInfo(model=self.model)
        
        # LangChain 的响应可能包含 response_metadata
        if hasattr(response, 'response_metadata'):
            metadata = response.response_metadata
            token_usage = metadata.get('token_usage', {})
            usage.input_tokens = token_usage.get('prompt_tokens', 0)
            usage.output_tokens = token_usage.get('completion_tokens', 0)
            usage.total_tokens = token_usage.get('total_tokens', 0)
        
        # 也可能在 usage_metadata 中
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage.input_tokens = response.usage_metadata.get('input_tokens', usage.input_tokens)
            usage.output_tokens = response.usage_metadata.get('output_tokens', usage.output_tokens)
            usage.total_tokens = response.usage_metadata.get('total_tokens', usage.total_tokens)
        
        return usage
    
    async def plan_topics(self, topic_direction: str) -> Tuple[List[str], LLMUsageInfo]:
        """
        根据主题方向生成候选选题
        
        Args:
            topic_direction: 用户输入的主题方向
            
        Returns:
            (生成的选题列表, token使用信息)
        """
        system_prompt = """你是一位专业的小红书内容策划专家。
你的任务是根据用户提供的主题方向，生成5个适合小红书平台的选题。

要求：
1. 选题要有吸引力，符合小红书用户的阅读习惯
2. 标题简洁有力，能引发好奇心
3. 选题要有实用价值或情感共鸣
4. 每个选题一行，不要编号，不要额外解释

请直接输出5个选题，每行一个。"""

        user_prompt = f"主题方向：{topic_direction if topic_direction else '技术分享'}"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        
        # 提取 token 使用信息
        usage = self._extract_usage_info(response)
        
        # 解析响应，按行分割获取选题列表
        topics = [
            line.strip() 
            for line in response.content.strip().split('\n') 
            if line.strip()
        ]
        
        # 确保返回至少5个选题
        topics = topics[:5] if len(topics) >= 5 else topics
        return topics, usage
    
    async def write_draft(
        self,
        topic: str,
        feedback: str = "",
        revision_count: int = 0
    ) -> Tuple[str, LLMUsageInfo]:
        """
        根据选题生成文章草稿
        
        Args:
            topic: 选中的选题
            feedback: 用户的修改意见（用于修订）
            revision_count: 当前修订次数
            
        Returns:
            (生成的文章内容, token使用信息)
        """
        system_prompt = """你是一位专业的小红书内容创作者。
你的任务是根据给定的选题，创作一篇高质量的小红书文章。

文章要求：
1. 开头要有吸引力，能抓住读者注意力
2. 内容有干货，提供实用价值
3. 语言风格轻松活泼，适合小红书平台
4. 适当使用emoji增加可读性
5. 结构清晰，分段合理
6. 字数控制在800-1500字
7. 结尾可以有互动引导（如提问、征集意见等）

请直接输出文章内容，使用Markdown格式。"""

        if feedback and revision_count > 0:
            user_prompt = f"""选题：{topic}

这是第 {revision_count} 次修订。请根据以下修改意见调整文章：

修改意见：{feedback}

请在保持文章整体结构的基础上，针对性地进行修改，并在文章开头简要说明修改内容。"""
        else:
            user_prompt = f"选题：{topic}\n\n请根据这个选题创作一篇小红书文章。"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        
        # 提取 token 使用信息
        usage = self._extract_usage_info(response)
        
        return response.content, usage
    
    async def extract_visual_points(self, article_content: str) -> Tuple[List[str], LLMUsageInfo]:
        """
        从文章中提取适合配图的要点
        
        Args:
            article_content: 文章内容
            
        Returns:
            (图片文案要点列表, token使用信息)
        """
        system_prompt = """你是一位专业的视觉内容策划师。
你的任务是分析文章内容，提取出3个适合配图的要点。

要求：
1. 每个要点应该能够转化为一张有意义的配图
2. 要点描述要具体，便于图片生成
3. 第一个要点作为封面图
4. 每个要点一行，不要编号
5. 描述格式：图片类型 + 具体内容描述

请直接输出3个配图要点，每行一个。"""

        user_prompt = f"请分析以下文章，提取配图要点：\n\n{article_content[:2000]}"  # 限制长度
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        
        # 提取 token 使用信息
        usage = self._extract_usage_info(response)
        
        # 解析响应
        points = [
            line.strip() 
            for line in response.content.strip().split('\n') 
            if line.strip()
        ]
        
        points = points[:3] if len(points) >= 3 else points
        return points, usage


# 创建单例实例
llm_service = LLMService()
