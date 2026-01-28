"""
图片生成测试接口
方便验证方舟 Doubao 图片生成是否可用
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services import get_image_service

router = APIRouter(prefix="/image", tags=["Image"])


class GenerateImageRequest(BaseModel):
    prompt: str = Field(..., description="图片描述文案")
    size: str = Field("2k", description="图片尺寸，示例：2k")


class GenerateImageResponse(BaseModel):
    url: str = Field(..., description="生成的图片 URL")
    model: str = Field(..., description="使用的图片模型")


@router.post("/generate", response_model=GenerateImageResponse)
async def generate_image(req: GenerateImageRequest) -> GenerateImageResponse:
    """
    生成单张图片（用于连通性测试）
    """
    try:
        image_service = get_image_service()
        url = await image_service.generate_single_image(
            prompt=req.prompt,
            size=req.size,
        )

        # 尝试暴露模型名称，便于排查
        model_name = getattr(image_service, "model", "unknown")

        return GenerateImageResponse(url=url, model=model_name)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"图片生成失败: {str(e)}",
        ) from e
