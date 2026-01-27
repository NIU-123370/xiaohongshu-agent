"""
LangGraph 状态定义模块
定义工作流中流转的状态结构

LangGraph 1.0+ 推荐使用 TypedDict 定义状态
"""
from typing import TypedDict, List, Literal, Annotated
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """
    AI 内容运营助手的状态定义
    
    LangGraph 1.0+ 使用 TypedDict 定义状态结构
    total=False 表示所有字段都是可选的
    
    Attributes:
        topic_direction: 用户初始输入的主题方向
        generated_topics: AI 生成的候选选题列表
        selected_topic: 用户选中的选题
        article_content: AI 生成的文章内容
        review_feedback: 用户的审核反馈意见
        review_status: 审核状态 (pending/approved/rejected)
        revision_count: 修改次数
        visual_points: 从文章中提取的图片文案要点
        image_urls: 生成的图片 URL 列表
        status: 当前工作流状态描述
        error: 错误信息（如果有）
    """
    # 选题阶段
    topic_direction: str
    generated_topics: List[str]
    selected_topic: str
    
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


# 状态初始值
INITIAL_STATE: AgentState = {
    "topic_direction": "",
    "generated_topics": [],
    "selected_topic": "",
    "article_content": "",
    "review_feedback": "",
    "review_status": "pending",
    "revision_count": 0,
    "visual_points": [],
    "image_urls": [],
    "status": "initialized",
    "error": "",
}
