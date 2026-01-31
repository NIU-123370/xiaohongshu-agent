"""
LangGraph 状态定义模块
定义工作流中流转的状态结构

LangGraph 1.0+ 推荐使用 TypedDict 定义状态
"""
from typing import TypedDict, List, Literal, Annotated, Dict, Any
from langgraph.graph.message import add_messages


class NodeMetric(TypedDict, total=False):
    """
    单个节点的执行指标
    
    Attributes:
        node_name: 节点名称
        duration_ms: 执行耗时(毫秒)
        input_tokens: 输入token数量
        output_tokens: 输出token数量
        total_tokens: 总token数量
        start_time: 开始时间(ISO格式)
        end_time: 结束时间(ISO格式)
        model: 使用的模型名称
    """
    node_name: str
    duration_ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    start_time: str
    end_time: str
    model: str


class TopicItemDict(TypedDict, total=False):
    """
    结构化选题项
    
    Attributes:
        title: 选题标题
        summary: 选题摘要
        keywords: 关键词列表
    """
    title: str
    summary: str
    keywords: List[str]


class AgentState(TypedDict, total=False):
    """
    AI 内容运营助手的状态定义
    
    LangGraph 1.0+ 使用 TypedDict 定义状态结构
    total=False 表示所有字段都是可选的
    
    Attributes:
        topic_direction: 用户初始输入的主题方向
        generated_topics: AI 生成的候选选题列表（兼容旧格式的标题列表）
        generated_topics_structured: AI 生成的结构化选题列表（包含标题、摘要、关键词）
        selected_topic: 用户选中的选题
        selected_topic_summary: 选中选题的摘要
        article_content: AI 生成的文章内容
        review_feedback: 用户的审核反馈意见
        review_status: 审核状态 (pending/approved/rejected)
        revision_count: 修改次数
        visual_points: 从文章中提取的图片文案要点
        image_urls: 生成的图片 URL 列表
        status: 当前工作流状态描述
        error: 错误信息（如果有）
        node_metrics: 各节点执行指标
    """
    # 选题阶段
    topic_direction: str
    generated_topics: List[str]  # 兼容旧格式：仅标题列表
    generated_topics_structured: List[TopicItemDict]  # 新格式：结构化选题
    selected_topic: str
    selected_topic_summary: str  # 选中选题的摘要
    
    # 写作阶段
    article_content: str
    review_feedback: str
    review_status: Literal["pending", "approved", "rejected"]
    revision_count: int
    
    # 视觉阶段
    visual_points: List[str]
    image_urls: List[str]
    
    # 工作流元数据
    status: str
    error: str
    
    # 节点执行指标
    node_metrics: List[NodeMetric]


# 状态初始值
INITIAL_STATE: AgentState = {
    "topic_direction": "",
    "generated_topics": [],
    "generated_topics_structured": [],
    "selected_topic": "",
    "selected_topic_summary": "",
    "article_content": "",
    "review_feedback": "",
    "review_status": "pending",
    "revision_count": 0,
    "visual_points": [],
    "image_urls": [],
    "status": "initialized",
    "error": "",
    "node_metrics": [],
}
