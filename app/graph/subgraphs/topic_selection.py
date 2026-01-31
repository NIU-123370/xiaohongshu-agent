"""
选题子图模块 (Topic Selection Subgraph)

将选题相关的逻辑封装为独立的子图，包含：
1. AI 生成选题 (plan_topics)
2. 人工选择选题 (human_select_topic) - 使用 interrupt

LangGraph 1.0+ 语法
"""
from typing import Literal, Dict, Any
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command

from app.graph.state import AgentState
from app.graph.nodes import plan_topics_node


async def human_select_topic_node(state: AgentState) -> Command[Literal["__end__"]]:
    """
    人工选题节点 (使用 LangGraph 1.0+ interrupt 模式)
    
    使用 interrupt() 暂停执行，等待人工输入选题
    
    Args:
        state: 当前工作流状态
        
    Returns:
        Command 对象，包含状态更新，goto END 结束子图
    """
    generated_topics = state.get("generated_topics", [])
    generated_topics_structured = state.get("generated_topics_structured", [])
    
    # 使用 interrupt 暂停，等待用户选择
    # 用户通过 update_state 提供 selected_topic 后，workflow resume
    # 中断信息包含结构化选题数据
    user_input = interrupt({
        "message": "请从以下选题中选择一个",
        "options": generated_topics,  # 兼容旧格式
        "options_structured": generated_topics_structured,  # 新结构化格式
        "action_required": "select_topic"
    })
    
    # 当用户通过 Command 恢复时，user_input 包含用户的选择
    selected_topic = user_input.get("selected_topic", "") if isinstance(user_input, dict) else ""
    
    # 如果用户选择了某个选题，尝试查找对应的摘要
    selected_topic_summary = ""
    if selected_topic and generated_topics_structured:
        for topic in generated_topics_structured:
            if topic.get("title") == selected_topic:
                selected_topic_summary = topic.get("summary", "")
                break
    
    return Command(
        update={
            "selected_topic": selected_topic,
            "selected_topic_summary": selected_topic_summary,
            "status": "topic_selected",
        },
        goto=END  # 结束子图，返回主图
    )


def build_topic_selection_subgraph() -> StateGraph:
    """
    构建选题子图
    
    子图工作流逻辑：
    1. Start -> plan_topics (AI 生成选题)
    2. plan_topics -> human_select_topic (等待人工选题，使用 interrupt())
    3. human_select_topic -> End (选题完成，返回主图)
    
    Returns:
        StateGraph 实例 (未编译)
    """
    # 创建子图，使用与主图相同的状态类型
    subgraph = StateGraph(AgentState)
    
    # 添加节点
    subgraph.add_node("plan_topics", plan_topics_node)
    subgraph.add_node("human_select_topic", human_select_topic_node)
    
    # 添加边
    # Start -> plan_topics
    subgraph.add_edge(START, "plan_topics")
    
    # plan_topics -> human_select_topic
    subgraph.add_edge("plan_topics", "human_select_topic")
    
    # human_select_topic 使用 Command(goto=END) 结束子图
    
    return subgraph


def get_compiled_topic_selection_subgraph():
    """
    获取编译后的选题子图
    
    注意：作为子图使用时，不需要单独的 checkpointer，
    主图的 checkpointer 会管理整个工作流的状态
    
    Returns:
        编译后的 CompiledStateGraph 实例
    """
    subgraph = build_topic_selection_subgraph()
    return subgraph.compile()
