"""
服务模块
提供 LLM 和图片生成等服务的统一接口
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def get_llm_service():
    """
    根据配置获取 LLM 服务实例
    
    Returns:
        LLM 服务实例（真实API或Mock）
    """
    use_mock = os.getenv("USE_MOCK_LLM", "true").lower() == "true"
    
    if use_mock:
        from app.services.llm_mock import mock_llm_service
        return mock_llm_service
    else:
        from app.services.llm_service import llm_service
        return llm_service


def get_image_service():
    """
    获取图片服务实例
    
    Returns:
        图片服务实例（真实API或Mock）
    """
    # 复用 LLM 的 Mock 开关；如需单独控制，可新增 USE_MOCK_IMAGE 环境变量
    use_mock = os.getenv("USE_MOCK_IMAGE", os.getenv("USE_MOCK_LLM", "true")).lower() == "true"

    if use_mock:
        from app.services.image_mock import mock_image_service
        return mock_image_service
    else:
        from app.services.image_service import image_service
        return image_service
