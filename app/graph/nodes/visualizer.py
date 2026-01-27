"""
视觉内容生成节点
负责从文章中提取配图要点并生成图片
"""
from typing import Dict, Any
from app.graph.state import AgentState
from app.services.llm_mock import mock_llm_service
from app.services.image_mock import mock_image_service


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
        # 调用 Mock LLM 服务提取视觉要点
        visual_points = await mock_llm_service.extract_visual_points(article_content)
        
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
        # 调用 Mock 图片服务生成配图
        image_urls = await mock_image_service.generate_images(visual_points)
        
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
