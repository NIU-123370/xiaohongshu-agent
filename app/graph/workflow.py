"""
LangGraph 工作流定义模块
组装完整的 AI 内容运营工作流

LangGraph 1.0+ 语法
"""
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command

from app.graph.state import AgentState
from app.graph.nodes import (
    plan_topics_node,
    write_draft_node,
    extract_visuals_node,
    generate_images_node,
)
from app.graph.utils import get_checkpointer


def should_continue_after_review(state: AgentState) -> Literal["extract_visuals", "write_draft"]:
    """
    审稿后的条件路由
    
    根据审核状态决定是继续生成配图还是回退重写
    
    Args:
        state: 当前工作流状态
        
    Returns:
        下一个节点名称
    """
    review_status = state.get("review_status", "pending")
    
    if review_status == "approved":
        return "extract_visuals"
    else:
        # rejected 或 pending 都回到写作节点
        return "write_draft"


async def human_select_topic_node(state: AgentState) -> Command[Literal["write_draft"]]:
    """
    人工选题节点 (使用 LangGraph 1.0+ interrupt 模式)
    
    使用 interrupt() 暂停执行，等待人工输入选题
    
    Args:
        state: 当前工作流状态
        
    Returns:
        Command 对象，包含状态更新和下一个节点
    """
    generated_topics = state.get("generated_topics", [])
    
    # 使用 interrupt 暂停，等待用户选择
    # 用户通过 update_state 提供 selected_topic 后，workflow resume
    user_input = interrupt({
        "message": "请从以下选题中选择一个",
        "options": generated_topics,
        "action_required": "select_topic"
    })
    
    # 当用户通过 Command 恢复时，user_input 包含用户的选择
    selected_topic = user_input.get("selected_topic", "") if isinstance(user_input, dict) else ""
    
    return Command(
        update={
            "selected_topic": selected_topic,
            "status": "topic_selected",
        },
        goto="write_draft"
    )


async def human_review_node(state: AgentState) -> Command[Literal["extract_visuals", "write_draft"]]:
    """
    人工审稿节点 (使用 LangGraph 1.0+ interrupt 模式)
    
    使用 interrupt() 暂停执行，等待人工审核
    
    Args:
        state: 当前工作流状态
        
    Returns:
        Command 对象，根据审核结果决定下一步
    """
    article_content = state.get("article_content", "")
    
    # 使用 interrupt 暂停，等待用户审核
    user_input = interrupt({
        "message": "请审核以下文章内容",
        "article_preview": article_content[:500] + "..." if len(article_content) > 500 else article_content,
        "action_required": "review",
        "options": ["approve", "reject"]
    })
    
    # 解析用户的审核结果
    if isinstance(user_input, dict):
        action = user_input.get("action", "reject")
        feedback = user_input.get("feedback", "")
    else:
        action = "reject"
        feedback = ""
    
    if action == "approve":
        return Command(
            update={
                "review_status": "approved",
                "review_feedback": "",
                "status": "review_approved",
            },
            goto="extract_visuals"
        )
    else:
        return Command(
            update={
                "review_status": "rejected",
                "review_feedback": feedback,
                "status": "review_rejected",
            },
            goto="write_draft"
        )


def build_workflow_graph() -> StateGraph:
    """
    构建工作流图 (LangGraph 1.0+ 语法)
    
    工作流逻辑：
    1. Start -> plan_topics (AI 生成选题)
    2. INTERRUPT: human_select_topic (等待人工选题，使用 interrupt())
    3. human_select_topic -> write_draft (AI 写文章)
    4. INTERRUPT: human_review (等待人工审稿，使用 interrupt())
    5. human_review -> 条件路由:
       - approved: extract_visuals -> generate_images -> End
       - rejected: 回到 write_draft (重写)
    
    Returns:
        StateGraph 实例
    """
    # 创建状态图
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("plan_topics", plan_topics_node)
    workflow.add_node("human_select_topic", human_select_topic_node)
    workflow.add_node("write_draft", write_draft_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("extract_visuals", extract_visuals_node)
    workflow.add_node("generate_images", generate_images_node)
    
    # 添加边
    # Start -> plan_topics
    workflow.add_edge(START, "plan_topics")
    
    # plan_topics -> human_select_topic
    workflow.add_edge("plan_topics", "human_select_topic")
    
    # human_select_topic 使用 Command 动态路由到 write_draft
    
    # write_draft -> human_review
    workflow.add_edge("write_draft", "human_review")
    
    # human_review 使用 Command 动态路由 (approved -> extract_visuals, rejected -> write_draft)
    
    # extract_visuals -> generate_images
    workflow.add_edge("extract_visuals", "generate_images")
    
    # generate_images -> End
    workflow.add_edge("generate_images", END)
    
    return workflow


async def get_compiled_graph():
    """
    获取编译后的工作流图（带持久化）
    
    LangGraph 1.0+ 使用 interrupt() 函数实现中断，
    不再需要 interrupt_before 参数
    
    Returns:
        编译后的 CompiledStateGraph 实例
    """
    # 获取 Checkpointer
    checkpointer = await get_checkpointer()
    
    # 构建工作流图
    workflow = build_workflow_graph()
    
    # 编译图，配置持久化
    # LangGraph 1.0+ 中断由 interrupt() 函数控制，不需要 interrupt_before
    compiled_graph = workflow.compile(
        checkpointer=checkpointer,
    )
    
    return compiled_graph


# 用于存储编译后的图实例
_compiled_graph = None


async def get_graph():
    """
    获取或创建编译后的图实例（单例模式）
    
    Returns:
        编译后的 CompiledStateGraph 实例
    """
    global _compiled_graph
    
    if _compiled_graph is None:
        _compiled_graph = await get_compiled_graph()
    
    return _compiled_graph


async def reset_graph():
    """
    重置图实例（用于重新初始化）
    """
    global _compiled_graph
    _compiled_graph = None
