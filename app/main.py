"""
FastAPI 应用入口
AI 内容运营助手后端服务
"""
import sys
from pathlib import Path

# 确保 backend 目录在 Python 路径中
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import init_db, close_db
from app.graph.utils import setup_checkpointer, close_checkpointer
from app.api.v1.workflow import router as workflow_router
from app.api.v1.image import router as image_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理
    
    启动时：
    - 初始化数据库连接
    - 初始化 LangGraph Checkpointer（创建必要的表）
    
    关闭时：
    - 关闭数据库连接
    - 关闭 Checkpointer 连接池
    """
    # 启动时执行
    print(f"🚀 正在启动 {settings.app_name}...")
    
    try:
        # 初始化 SQLAlchemy 数据库
        print("📦 初始化数据库连接...")
        await init_db()
        
        # 初始化 LangGraph Checkpointer
        print("🔧 初始化 LangGraph Checkpointer...")
        await setup_checkpointer()
        print("✅ Checkpointer 表结构已创建/验证")
        
        print(f"✅ {settings.app_name} 启动成功!")
        print(f"📖 API 文档: http://localhost:8000/docs")
        
    except Exception as e:
        print(f"❌ 启动失败: {str(e)}")
        raise
    
    yield
    
    # 关闭时执行
    print(f"🛑 正在关闭 {settings.app_name}...")
    
    try:
        await close_checkpointer()
        await close_db()
        print("✅ 资源已释放")
    except Exception as e:
        print(f"⚠️ 关闭时出错: {str(e)}")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    description="""
## AI 内容运营助手 API

为教育培训公司提供的自动化内容生成工作流服务。

### 核心功能

- **选题生成**: AI 根据主题方向生成多个候选选题
- **文章撰写**: AI 根据选定选题生成技术文章
- **人工审核**: 支持通过/驳回机制，驳回后可重写
- **配图生成**: 自动提取视觉要点并生成配图

### 工作流程

1. 启动工作流，AI 生成候选选题
2. 人工选择一个选题
3. AI 生成文章草稿
4. 人工审核（通过/驳回）
5. 通过后自动生成配图
    """,
    version="1.0.0",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(workflow_router, prefix="/api/v1")
app.include_router(image_router, prefix="/api/v1")


@app.get("/")
async def root():
    """根路径 - 服务健康检查"""
    return {
        "service": settings.app_name,
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "service": settings.app_name
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
