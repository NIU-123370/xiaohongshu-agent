"""
选题规划节点
负责根据用户输入的主题方向生成候选选题
"""
from typing import Dict, Any
from app.graph.state import AgentState
from app.services import get_llm_service


async def plan_topics_node(state: AgentState) -> Dict[str, Any]:
    """
    选题规划节点
    
    根据用户输入的主题方向，调用 LLM 生成候选选题列表
    
    Args:
        state: 当前工作流状态
        
    Returns:
        更新后的状态字段
    """
    topic_direction = state.get("topic_direction", "")
    
    try:
        # 获取 LLM 服务（根据配置自动选择真实API或Mock）
        llm_service = get_llm_service()
        generated_topics = await llm_service.plan_topics(topic_direction)
        
        return {
            "generated_topics": generated_topics,
            "status": "topics_generated",
            "error": "",
        }
        
    except Exception as e:
        return {
            "generated_topics": [],
            "status": "error",
            "error": f"生成选题失败: {str(e)}",
        }
