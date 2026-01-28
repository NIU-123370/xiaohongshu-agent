"""
文章写作节点
负责根据选定的选题生成文章内容
"""
from typing import Dict, Any
from app.graph.state import AgentState
from app.services import get_llm_service


async def write_draft_node(state: AgentState) -> Dict[str, Any]:
    """
    文章写作节点
    
    根据选定的选题，调用 LLM 生成文章草稿
    如果有修改意见，则根据意见进行修订
    
    Args:
        state: 当前工作流状态
        
    Returns:
        更新后的状态字段
    """
    selected_topic = state.get("selected_topic", "")
    review_feedback = state.get("review_feedback", "")
    revision_count = state.get("revision_count", 0)
    
    if not selected_topic:
        return {
            "article_content": "",
            "status": "error",
            "error": "未选择选题，无法生成文章",
        }
    
    try:
        # 如果有修改意见，增加修订计数
        if review_feedback:
            revision_count += 1
        
        # 获取 LLM 服务（根据配置自动选择真实API或Mock）
        llm_service = get_llm_service()
        article_content = await llm_service.write_draft(
            topic=selected_topic,
            feedback=review_feedback,
            revision_count=revision_count
        )
        
        return {
            "article_content": article_content,
            "revision_count": revision_count,
            "review_status": "pending",
            "status": "draft_generated",
            "error": "",
        }
        
    except Exception as e:
        return {
            "article_content": "",
            "status": "error",
            "error": f"生成文章失败: {str(e)}",
        }
