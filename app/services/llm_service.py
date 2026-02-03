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

# PII 脱敏 callback（延迟导入避免循环依赖）
def _get_pii_callback():
    """获取 PII 脱敏回调（延迟导入）"""
    try:
        from app.core.callbacks import pii_callback
        return pii_callback
    except ImportError:
        return None


# ============== 结构化输出 Pydantic 模型 ==============

class TopicItem(BaseModel):
    """单个选题项"""
    title: str = Field(..., description="选题标题，简洁有力，能引发好奇心")


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
    """LLM 服务类 - 使用火山引擎 Doubao API，支持多模型"""
    
    def __init__(self, enable_pii_anonymize: bool = True):
        """
        初始化 LLM 服务
        
        支持两种模型：
        - 标准模型 (llm): 用于文章写作，需要高质量输出
        - 快速模型 (llm_fast): 用于选题生成、配图要点提取，追求速度
        
        Args:
            enable_pii_anonymize: 是否启用 PII 脱敏
        """
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
        
        # 标准模型配置 (文章写作)
        self.model = os.getenv("LLM_MODEL", "doubao-seed-1-8-251228")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
        
        # 快速模型配置 (选题、配图要点)
        self.model_fast = os.getenv("LLM_MODEL_FAST", "doubao-seed-1-6-flash-250828")
        self.temperature_fast = float(os.getenv("LLM_TEMPERATURE_FAST", "0.7"))
        self.temperature_extract = float(os.getenv("LLM_TEMPERATURE_EXTRACT", "0.4"))
        
        self.enable_pii_anonymize = enable_pii_anonymize
        
        # 初始化 LLM 客户端（懒加载）
        self._llm = None
        self._llm_fast = None
        self._llm_extract = None
        
        # 启动时输出模型配置
        print(f"[LLM] 模型配置:")
        print(f"  - 标准模型(文章): {self.model}")
        print(f"  - 快速模型(选题): {self.model_fast}")
    
    def _get_callbacks(self) -> List:
        """获取回调列表"""
        callbacks = []
        if self.enable_pii_anonymize:
            pii_callback = _get_pii_callback()
            if pii_callback:
                callbacks.append(pii_callback)
        return callbacks
    
    @property
    def llm(self) -> ChatOpenAI:
        """懒加载标准 LLM 客户端（文章写作用）"""
        if self._llm is None:
            callbacks = self._get_callbacks()
            self._llm = ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                api_key=self.api_key,
                base_url=self.base_url,
                callbacks=callbacks if callbacks else None,
            )
        return self._llm
    
    @property
    def llm_fast(self) -> ChatOpenAI:
        """懒加载快速 LLM 客户端（选题生成用）"""
        if self._llm_fast is None:
            callbacks = self._get_callbacks()
            self._llm_fast = ChatOpenAI(
                model=self.model_fast,
                temperature=self.temperature_fast,
                api_key=self.api_key,
                base_url=self.base_url,
                callbacks=callbacks if callbacks else None,
            )
        return self._llm_fast
    
    @property
    def llm_extract(self) -> ChatOpenAI:
        """懒加载提取用 LLM 客户端（配图要点提取用，temperature 较低）"""
        if self._llm_extract is None:
            callbacks = self._get_callbacks()
            self._llm_extract = ChatOpenAI(
                model=self.model_fast,  # 使用快速模型
                temperature=self.temperature_extract,  # 较低的 temperature
                api_key=self.api_key,
                base_url=self.base_url,
                callbacks=callbacks if callbacks else None,
            )
        return self._llm_extract
    
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
        
        使用快速模型 (llm_fast) 提高响应速度
        使用 with_structured_output(include_raw=True) 同时获取结构化输出和原始响应
        
        Args:
            topic_direction: 用户输入的主题方向
            
        Returns:
            (TopicsResponse 结构化选题响应, token使用信息)
        """
        # 小红书风格提示词：强调爆款特征和情绪共鸣
        system_prompt = """你是小红书10w+爆款标题专家，精通平台流量密码。

根据主题方向生成5个超有吸引力的爆款选题标题。

【爆款标题公式】
1. 数字+痛点："3个方法让我..." "5分钟搞定..."
2. 悬念反转："原来xx这么简单" "后悔没早知道"
3. 情绪共鸣："救命！" "绝了！" "真的会谢"
4. 身份代入："打工人必看" "新手小白"
5. 对比冲击："花了3000学的vs我自己琢磨的"

【标题要求】
- 15字以内，一眼抓住注意力
- 口语化、接地气，像朋友聊天
- 用感叹号、问号增加情绪张力
- 可用 emoji 点缀（如🔥💡✨）

【示例】
主题：Python编程
爆款标题：
- 救命！零基础3天学会Python🔥
- 打工人偷偷学的Python技能✨
- 花2w报班 vs 我自学3个月
- 后悔没早知道的Python神器！
- 5个让代码效率翻倍的技巧💡"""

        user_prompt = f"主题：{topic_direction or '技术分享'}"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        usage = LLMUsageInfo(model=self.model_fast)
        parsed_response = None
        
        # 调试日志：输出实际使用的模型
        import time
        start_time = time.time()
        print(f"[LLM] plan_topics 开始调用，使用模型: {self.model_fast}")
        
        try:
            # 使用快速模型 + 结构化输出
            structured_llm = self.llm_fast.with_structured_output(TopicsResponse, include_raw=True)
            result = await structured_llm.ainvoke(messages)
            
            elapsed = time.time() - start_time
            print(f"[LLM] plan_topics 调用完成，耗时: {elapsed:.2f}s")
            
            raw_response = result.get('raw')
            parsed_response = result.get('parsed')
            
            if raw_response:
                usage = self._extract_usage_info(raw_response)
                usage.model = self.model_fast
                
        except Exception as e:
            print(f"[LLM] with_structured_output 失败，尝试 JSON 模式: {e}")
            
            try:
                structured_llm = self.llm_fast.with_structured_output(TopicsResponse, method="json_mode", include_raw=True)
                result = await structured_llm.ainvoke(messages)
                
                raw_response = result.get('raw')
                parsed_response = result.get('parsed')
                
                if raw_response:
                    usage = self._extract_usage_info(raw_response)
                    usage.model = self.model_fast
                    
            except Exception as e2:
                print(f"[LLM] JSON 模式也失败，使用备用方案: {e2}")
                parsed_response, usage = await self._plan_topics_fallback(topic_direction)
        
        if parsed_response is None:
            parsed_response = TopicsResponse(topics=[])
        
        return parsed_response, usage
    
    async def _plan_topics_fallback(self, topic_direction: str) -> Tuple[TopicsResponse, LLMUsageInfo]:
        """
        备用方案：通过 prompt 要求 JSON 输出并手动解析（使用快速模型）
        """
        import json
        import re
        
        system_prompt = """你是小红书10w+爆款标题专家。生成5个超吸引人的选题标题。

【爆款技巧】数字+痛点、悬念反转、情绪共鸣（救命/绝了）、身份代入（打工人/小白）
【要求】15字内、口语化、有情绪、可用emoji

JSON格式输出：{"topics":[{"title":"标题1"},{"title":"标题2"},{"title":"标题3"},{"title":"标题4"},{"title":"标题5"}]}"""

        user_prompt = f"主题：{topic_direction or '技术分享'}"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        # 使用快速模型
        response = await self.llm_fast.ainvoke(messages)
        usage = self._extract_usage_info(response)
        usage.model = self.model_fast
        
        # 解析 JSON
        try:
            content = response.content.strip()
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
        根据选题生成文章草稿（非流式，使用标准模型保证质量）
        
        Args:
            topic: 选中的选题
            feedback: 用户的修改意见（用于修订）
            revision_count: 当前修订次数
            
        Returns:
            (生成的文章内容, token使用信息)
        """
        # 优化后的提示词
        system_prompt = """你是小红书爆款文章创作者。

文章要求：
- 开头抓人：用故事/问题/数据引入
- 干货满满：提供可操作的价值
- 语言活泼：口语化，适当用emoji
- 结构清晰：分段合理，善用小标题
- 800-1200字
- 结尾互动：提问引导评论

直接输出Markdown格式文章。"""

        if feedback and revision_count > 0:
            user_prompt = f"选题：{topic}\n\n第{revision_count}次修订，修改意见：{feedback}\n\n请针对性修改。"
        else:
            user_prompt = f"选题：{topic}"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = await self.llm.ainvoke(messages)
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
        流式生成文章草稿，并统计 token 使用信息（使用标准模型保证质量）
        
        Args:
            topic: 选中的选题
            feedback: 用户的修改意见（用于修订）
            revision_count: 当前修订次数
            on_chunk: 可选的回调函数，每收到一个文本片段时调用
            
        Returns:
            StreamResult 包含完整内容和 token 统计
        """
        # 优化后的提示词
        system_prompt = """你是小红书爆款文章创作者。

文章要求：
- 开头抓人：用故事/问题/数据引入
- 干货满满：提供可操作的价值
- 语言活泼：口语化，适当用emoji
- 结构清晰：分段合理，善用小标题
- 800-1200字
- 结尾互动：提问引导评论

直接输出Markdown格式文章。"""

        if feedback and revision_count > 0:
            user_prompt = f"选题：{topic}\n\n第{revision_count}次修订，修改意见：{feedback}\n\n请针对性修改。"
        else:
            user_prompt = f"选题：{topic}"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        full_content = ""
        usage = LLMUsageInfo(model=self.model)
        
        async for chunk in self.llm.astream(messages):
            if isinstance(chunk, AIMessageChunk):
                if chunk.content:
                    full_content += chunk.content
                    if on_chunk:
                        on_chunk(chunk.content)
                
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
        流式生成文章草稿的生成器版本（使用标准模型保证质量）
        
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
        # 优化后的提示词
        system_prompt = """你是小红书爆款文章创作者。

文章要求：
- 开头抓人：用故事/问题/数据引入
- 干货满满：提供可操作的价值
- 语言活泼：口语化，适当用emoji
- 结构清晰：分段合理，善用小标题
- 800-1200字
- 结尾互动：提问引导评论

直接输出Markdown格式文章。"""

        if feedback and revision_count > 0:
            user_prompt = f"选题：{topic}\n\n第{revision_count}次修订，修改意见：{feedback}\n\n请针对性修改。"
        else:
            user_prompt = f"选题：{topic}"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        chunks: List[AIMessageChunk] = []
        full_content = ""
        usage = LLMUsageInfo(model=self.model)
        
        async for chunk in self.llm.astream(messages):
            if isinstance(chunk, AIMessageChunk):
                chunks.append(chunk)
                if chunk.content:
                    full_content += chunk.content
                    yield (chunk.content, None)
                
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
        
        if usage.total_tokens == 0:
            usage.input_tokens = len(system_prompt + user_prompt) // 2
            usage.output_tokens = len(full_content) // 2
            usage.total_tokens = usage.input_tokens + usage.output_tokens
        
        yield ("", usage)
    
    async def extract_visual_points(self, article_content: str) -> Tuple[List[str], LLMUsageInfo]:
        """
        从文章中提取适合配图的要点（使用快速模型 + 低 temperature）
        
        Args:
            article_content: 文章内容
            
        Returns:
            (图片文案要点列表, token使用信息)
        """
        # 优化后的提示词：更简洁
        system_prompt = """为AI图片生成工具提取3个配图描述。

格式要求：
- 纯视觉描述，含场景、色彩、风格
- 第一个为封面图，需吸引眼球
- 每行一个，不编号

风格：插画/扁平化/简约现代/温馨治愈
禁止：文字内容、敏感政治暴力内容"""

        # 限制文章长度，减少 token
        truncated_content = article_content[:1500] if len(article_content) > 1500 else article_content
        user_prompt = f"文章内容：\n{truncated_content}"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        # 使用提取专用模型（快速模型 + 低 temperature）
        response = await self.llm_extract.ainvoke(messages)
        
        usage = self._extract_usage_info(response)
        usage.model = self.model_fast
        
        # 解析响应
        points = [
            line.strip() 
            for line in response.content.strip().split('\n') 
            if line.strip() and not line.strip().startswith('-')
        ]
        
        # 清理可能的编号前缀
        cleaned_points = []
        for p in points:
            # 移除 "1." "2." 等编号
            import re
            cleaned = re.sub(r'^\d+[\.\)]\s*', '', p)
            if cleaned:
                cleaned_points.append(cleaned)
        
        return cleaned_points[:3], usage

    # ============== 流式输出方法 ==============
    
    async def stream_plan_topics(self, topic_direction: str) -> AsyncGenerator[str, None]:
        """
        流式生成候选选题（使用快速模型）
        
        Args:
            topic_direction: 用户输入的主题方向
            
        Yields:
            生成的文本片段
        """
        system_prompt = """你是小红书10w+爆款标题专家。生成5个超吸引人的选题，每行一个。

【爆款技巧】数字+痛点、悬念反转、情绪共鸣（救命/绝了/真的会谢）、身份代入（打工人/小白）、可用emoji
【要求】15字内、口语化接地气、像朋友聊天、有感叹号问号增加情绪"""

        user_prompt = f"主题：{topic_direction or '技术分享'}"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        # 使用快速模型
        async for chunk in self.llm_fast.astream(messages):
            if chunk.content:
                yield chunk.content

    async def stream_write_draft(
        self,
        topic: str,
        feedback: str = "",
        revision_count: int = 0
    ) -> AsyncGenerator[str, None]:
        """
        流式生成文章草稿（使用标准模型保证质量）
        
        Args:
            topic: 选中的选题
            feedback: 用户的修改意见（用于修订）
            revision_count: 当前修订次数
            
        Yields:
            生成的文本片段
        """
        system_prompt = """你是小红书爆款文章创作者。

文章要求：
- 开头抓人：用故事/问题/数据引入
- 干货满满：提供可操作的价值
- 语言活泼：口语化，适当用emoji
- 结构清晰：分段合理，善用小标题
- 800-1200字
- 结尾互动：提问引导评论

直接输出Markdown格式文章。"""

        if feedback and revision_count > 0:
            user_prompt = f"选题：{topic}\n\n第{revision_count}次修订，修改意见：{feedback}\n\n请针对性修改。"
        else:
            user_prompt = f"选题：{topic}"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        async for chunk in self.llm.astream(messages):
            if chunk.content:
                yield chunk.content

    async def stream_extract_visual_points(self, article_content: str) -> AsyncGenerator[str, None]:
        """
        流式提取配图要点（使用快速模型 + 低 temperature）
        
        Args:
            article_content: 文章内容
            
        Yields:
            生成的文本片段
        """
        system_prompt = """为AI图片生成工具提取3个配图描述。
格式：纯视觉描述，含场景、色彩、风格，每行一个，不编号。
风格：插画/扁平化/简约现代/温馨治愈
禁止：文字内容、敏感政治暴力内容"""

        truncated_content = article_content[:1500] if len(article_content) > 1500 else article_content
        user_prompt = f"文章：\n{truncated_content}"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        # 使用提取专用模型
        async for chunk in self.llm_extract.astream(messages):
            if chunk.content:
                yield chunk.content


# 创建单例实例
llm_service = LLMService()
