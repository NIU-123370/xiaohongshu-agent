"""
LangGraph 工具函数模块
包含 Checkpointer 初始化等工具函数

LangGraph 1.0+ 语法

注意：当前使用 MemorySaver (内存版 Checkpointer) 进行开发测试
生产环境请切换回 AsyncPostgresSaver
"""
from langgraph.checkpoint.memory import MemorySaver

# 是否使用 Mock 模式 (内存 Checkpointer)
USE_MOCK_CHECKPOINTER = True

# 全局 Checkpointer 实例
_checkpointer: MemorySaver | None = None


async def setup_checkpointer() -> MemorySaver:
    """
    设置并初始化 Checkpointer
    
    当前使用 MemorySaver (内存存储) 用于开发测试
    
    Returns:
        配置好的 MemorySaver 实例
    """
    global _checkpointer
    
    if _checkpointer is not None:
        return _checkpointer
    
    if USE_MOCK_CHECKPOINTER:
        # 使用内存版 Checkpointer (无需数据库)
        _checkpointer = MemorySaver()
        print("📝 使用 MemorySaver (内存模式) - 数据不会持久化")
    else:
        # TODO: 生产环境使用 PostgreSQL Checkpointer
        # from psycopg_pool import AsyncConnectionPool
        # from langgraph_checkpoint_postgres.aio import AsyncPostgresSaver
        # from app.core.config import settings
        # pool = AsyncConnectionPool(conninfo=settings.postgres_uri, ...)
        # _checkpointer = AsyncPostgresSaver(pool)
        # await _checkpointer.setup()
        raise NotImplementedError("PostgreSQL Checkpointer 未配置")
    
    return _checkpointer


async def get_checkpointer() -> MemorySaver:
    """
    获取已初始化的 Checkpointer 实例
    
    Returns:
        MemorySaver 实例
        
    Raises:
        RuntimeError: 如果 Checkpointer 未初始化
    """
    global _checkpointer
    
    if _checkpointer is None:
        return await setup_checkpointer()
    
    return _checkpointer


async def close_checkpointer() -> None:
    """
    关闭 Checkpointer (内存版无需特殊处理)
    """
    global _checkpointer
    _checkpointer = None
    print("📝 Checkpointer 已清理")
