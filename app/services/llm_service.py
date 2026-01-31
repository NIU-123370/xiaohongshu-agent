"""
LLM 服务模块
使用火山引擎 Doubao API 进行 LLM 调用
支持流式输出和结构化输出
"""
import os
from typing import List, Tuple, Optional, AsyncGenerator, Callable, Any
from dataclasses import dataclass, field
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessageChunk
from pydantic import BaseModel, Field

# 加载环境变量
load_dotenv()


# ============== 结构化输出 Pydantic 模型 ==============

class TopicItem(BaseModel):
    """单个选题项"""
    title: str = Field(..., description="选题标题，简洁有力，能引发好奇心")
    summary: str = Field(..., description="选题摘要，50-100字，说明文章主要内容和价值")
    keywords: List[str] = Field(default=[], description="关键词标签，3-5个")


class TopicsResponse(BaseModel):
    """选题响应结构"""
    topics: List[TopicItem] = Field(..., description="生成的选题列表")


@dataclass
class LLMUsageInfo:
    """LLM 调用的 token 使用信息"""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model: str = ""


@dataclass
class StreamResult:
    """流式输出结果，包含完整内容和 token 统计"""
    content: str = ""
    usage: LLMUsageInfo = field(default_factory=LLMUsageInfo)


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
    
    async def plan_topics(self, topic_direction: str) -> Tuple[TopicsResponse, LLMUsageInfo]:
        """
        根据主题方向生成候选选题（结构化输出 + token 统计）
        
        使用 with_structured_output(include_raw=True) 同时获取结构化输出和原始响应
        如果 API 不支持，则回退到 JSON 模式
        
        Args:
            topic_direction: 用户输入的主题方向
            
        Returns:
            (TopicsResponse 结构化选题响应, token使用信息)
        """
        system_prompt = """你是一位专业的小红书内容策划专家。
你的任务是根据用户提供的主题方向，生成5个适合小红书平台的选题。

要求：
1. 选题要有吸引力，符合小红书用户的阅读习惯
2. 标题简洁有力，能引发好奇心
3. 选题要有实用价值或情感共鸣
4. 为每个选题提供摘要（50-100字）和3-5个关键词

请生成5个选题，每个选题包含标题、摘要和关键词。"""

        user_prompt = f"主题方向：{topic_direction if topic_direction else '技术分享'}"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        usage = LLMUsageInfo(model=self.model)
        parsed_response = None
        
        try:
            # 方案1: 使用 with_structured_output + include_raw=True（需要 API 支持 function calling）
            structured_llm = self.llm.with_structured_output(TopicsResponse, include_raw=True)
            result = await structured_llm.ainvoke(messages)
            
            # result 是一个字典，包含 'raw' 和 'parsed' 两个键
            raw_response = result.get('raw')
            parsed_response = result.get('parsed')
            
            # 从原始响应中提取 token 使用信息
            if raw_response:
                usage = self._extract_usage_info(raw_response)
                
        except Exception as e:
            print(f"[LLM] with_structured_output 失败，尝试 JSON 模式: {e}")
            
            try:
                # 方案2: 使用 JSON 模式的结构化输出
                structured_llm = self.llm.with_structured_output(TopicsResponse, method="json_mode", include_raw=True)
                result = await structured_llm.ainvoke(messages)
                
                raw_response = result.get('raw')
                parsed_response = result.get('parsed')
                
                if raw_response:
                    usage = self._extract_usage_info(raw_response)
                    
            except Exception as e2:
                print(f"[LLM] JSON 模式也失败，使用备用方案: {e2}")
                # 方案3: 备用方案 - 直接调用并手动解析
                parsed_response, usage = await self._plan_topics_fallback(topic_direction)
        
        # 如果解析失败，返回空结果
        if parsed_response is None:
            parsed_response = TopicsResponse(topics=[])
        
        return parsed_response, usage
    
    async def _plan_topics_fallback(self, topic_direction: str) -> Tuple[TopicsResponse, LLMUsageInfo]:
        """
        备用方案：通过 prompt 要求 JSON 输出并手动解析
        """
        import json
        import re
        
        system_prompt = """你是一位专业的小红书内容策划专家。
你的任务是根据用户提供的主题方向，生成5个适合小红书平台的选题。

要求：
1. 选题要有吸引力，符合小红书用户的阅读习惯
2. 标题简洁有力，能引发好奇心
3. 选题要有实用价值或情感共鸣
4. 为每个选题提供摘要（50-100字）和3-5个关键词

请严格按照以下JSON格式输出，不要有其他内容：
{"topics":[{"title":"标题","summary":"摘要","keywords":["关键词1","关键词2"]}]}"""

        user_prompt = f"主题方向：{topic_direction if topic_direction else '技术分享'}"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
        usage = self._extract_usage_info(response)
        
        # 解析 JSON
        try:
            content = response.content.strip()
            # 提取 JSON 部分
            if "```" in content:
                content = re.sub(r'^.*?```(?:json)?\s*', '', content, flags=re.DOTALL)
                content = re.sub(r'\s*```.*$', '', content, flags=re.DOTALL)
            
            json_start = content.find('{')
            json_end = content.rfind('}')
            if json_start != -1 and json_end != -1:
                content = content[json_start:json_end + 1]
            
            data = json.loads(content)
            parsed_response = TopicsResponse(**data)
        except Exception as e:
            print(f"[LLM] JSON 解析失败: {e}, 内容: {response.content[:500]}")
            parsed_response = TopicsResponse(topics=[])
        
        return parsed_response, usage
    
    async def plan_topics_with_accurate_usage(self, topic_direction: str) -> Tuple[TopicsResponse, LLMUsageInfo]:
        """
        plan_topics 的别名方法，保持向后兼容
        """
        return await self.plan_topics(topic_direction)
    
    async def write_draft(
        self,
        topic: str,
        feedback: str = "",
        revision_count: int = 0
    ) -> Tuple[str, LLMUsageInfo]:
        """
        根据选题生成文章草稿（非流式，用于兼容）
        
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

    async def stream_write_draft_with_usage(
        self,
        topic: str,
        feedback: str = "",
        revision_count: int = 0,
        on_chunk: Optional[Callable[[str], Any]] = None
    ) -> StreamResult:
        """
        流式生成文章草稿，并统计 token 使用信息
        
        Args:
            topic: 选中的选题
            feedback: 用户的修改意见（用于修订）
            revision_count: 当前修订次数
            on_chunk: 可选的回调函数，每收到一个文本片段时调用
            
        Returns:
            StreamResult 包含完整内容和 token 统计
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
        
        # 流式输出并收集内容
        full_content = ""
        usage = LLMUsageInfo(model=self.model)
        
        # 使用 astream 进行流式输出，并在最后获取 usage
        async for chunk in self.llm.astream(messages):
            if isinstance(chunk, AIMessageChunk):
                if chunk.content:
                    full_content += chunk.content
                    if on_chunk:
                        on_chunk(chunk.content)
                
                # 尝试从最后一个 chunk 获取 usage_metadata
                if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                    usage.input_tokens = chunk.usage_metadata.get('input_tokens', 0)
                    usage.output_tokens = chunk.usage_metadata.get('output_tokens', 0)
                    usage.total_tokens = chunk.usage_metadata.get('total_tokens', 0)
                
                # 也检查 response_metadata
                if hasattr(chunk, 'response_metadata') and chunk.response_metadata:
                    token_usage = chunk.response_metadata.get('token_usage', {})
                    if token_usage:
                        usage.input_tokens = token_usage.get('prompt_tokens', usage.input_tokens)
                        usage.output_tokens = token_usage.get('completion_tokens', usage.output_tokens)
                        usage.total_tokens = token_usage.get('total_tokens', usage.total_tokens)
        
        # 如果没有获取到 usage，使用估算值
        if usage.total_tokens == 0:
            usage.input_tokens = len(system_prompt + user_prompt) // 2
            usage.output_tokens = len(full_content) // 2
            usage.total_tokens = usage.input_tokens + usage.output_tokens
        
        return StreamResult(content=full_content, usage=usage)

    async def stream_write_draft_generator(
        self,
        topic: str,
        feedback: str = "",
        revision_count: int = 0
    ) -> AsyncGenerator[Tuple[str, Optional[LLMUsageInfo]], None]:
        """
        流式生成文章草稿的生成器版本
        
        每次 yield 一个 (chunk, usage) 元组
        - 普通 chunk: (text, None)
        - 最后一个 chunk: (text, LLMUsageInfo)
        
        Args:
            topic: 选中的选题
            feedback: 用户的修改意见（用于修订）
            revision_count: 当前修订次数
            
        Yields:
            (文本片段, token使用信息或None)
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
        
        # 收集所有 chunks 以便在最后计算 usage
        chunks: List[AIMessageChunk] = []
        full_content = ""
        usage = LLMUsageInfo(model=self.model)
        
        async for chunk in self.llm.astream(messages):
            if isinstance(chunk, AIMessageChunk):
                chunks.append(chunk)
                if chunk.content:
                    full_content += chunk.content
                    yield (chunk.content, None)
                
                # 尝试从 chunk 获取 usage
                if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                    usage.input_tokens = chunk.usage_metadata.get('input_tokens', 0)
                    usage.output_tokens = chunk.usage_metadata.get('output_tokens', 0)
                    usage.total_tokens = chunk.usage_metadata.get('total_tokens', 0)
                
                if hasattr(chunk, 'response_metadata') and chunk.response_metadata:
                    token_usage = chunk.response_metadata.get('token_usage', {})
                    if token_usage:
                        usage.input_tokens = token_usage.get('prompt_tokens', usage.input_tokens)
                        usage.output_tokens = token_usage.get('completion_tokens', usage.output_tokens)
                        usage.total_tokens = token_usage.get('total_tokens', usage.total_tokens)
        
        # 如果没有获取到 usage，使用估算值
        if usage.total_tokens == 0:
            usage.input_tokens = len(system_prompt + user_prompt) // 2
            usage.output_tokens = len(full_content) // 2
            usage.total_tokens = usage.input_tokens + usage.output_tokens
        
        # 最后 yield 一个空字符串和 usage
        yield ("", usage)
    
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

    # ============== 流式输出方法 ==============
    
    async def stream_plan_topics(self, topic_direction: str) -> AsyncGenerator[str, None]:
        """
        流式生成候选选题
        
        Args:
            topic_direction: 用户输入的主题方向
            
        Yields:
            生成的文本片段
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
        
        async for chunk in self.llm.astream(messages):
            if chunk.content:
                yield chunk.content

    async def stream_write_draft(
        self,
        topic: str,
        feedback: str = "",
        revision_count: int = 0
    ) -> AsyncGenerator[str, None]:
        """
        流式生成文章草稿
        
        Args:
            topic: 选中的选题
            feedback: 用户的修改意见（用于修订）
            revision_count: 当前修订次数
            
        Yields:
            生成的文本片段
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
        
        async for chunk in self.llm.astream(messages):
            if chunk.content:
                yield chunk.content

    async def stream_extract_visual_points(self, article_content: str) -> AsyncGenerator[str, None]:
        """
        流式提取配图要点
        
        Args:
            article_content: 文章内容
            
        Yields:
            生成的文本片段
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

        user_prompt = f"请分析以下文章，提取配图要点：\n\n{article_content[:2000]}"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        async for chunk in self.llm.astream(messages):
            if chunk.content:
                yield chunk.content


# 创建单例实例
llm_service = LLMService()
