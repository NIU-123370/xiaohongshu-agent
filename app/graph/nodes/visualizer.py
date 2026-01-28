"""
视觉内容生成节点
负责从文章中提取配图要点并生成图片
"""
from typing import Dict, Any
from app.graph.state import AgentState
from app.services import get_llm_service, get_image_service


async def extract_visuals_node(state: AgentState) -> Dict[str, Any]:
    """
    提取视觉要点节点
    
    从文章内容中提取适合配图的要点
    
    Args:
        state: 当前工作流状态
        
    Returns:
        更新后的状态字段
    """
    article_content = state.get("article_content", "")
    
    if not article_content:
        return {
            "visual_points": [],
            "status": "error",
            "error": "文章内容为空，无法提取视觉要点",
        }
    
    try:
        # 获取 LLM 服务（根据配置自动选择真实API或Mock）
        llm_service = get_llm_service()
        visual_points = await llm_service.extract_visual_points(article_content)
        
        return {
            "visual_points": visual_points,
            "status": "visuals_extracted",
            "error": "",
        }
        
    except Exception as e:
        return {
            "visual_points": [],
            "status": "error",
            "error": f"提取视觉要点失败: {str(e)}",
        }


async def generate_images_node(state: AgentState) -> Dict[str, Any]:
    """
    生成配图节点
    
    根据视觉要点生成配图
    
    Args:
        state: 当前工作流状态
        
    Returns:
        更新后的状态字段
    """
    visual_points = state.get("visual_points", [])
    
    if not visual_points:
        return {
            "image_urls": [],
            "status": "error",
            "error": "视觉要点为空，无法生成配图",
        }
    
    try:
        # 获取图片服务（目前使用Mock，后续可接入真实API）
        image_service = get_image_service()
        image_urls = await image_service.generate_images(visual_points)
        
        return {
            "image_urls": image_urls,
            "status": "completed",
            "error": "",
        }
        
    except Exception as e:
        return {
            "image_urls": [],
            "status": "error",
            "error": f"生成配图失败: {str(e)}",
        }
