"""
数据库连接模块
配置 SQLAlchemy AsyncSession

注意：当前使用 Mock 模式，不连接真实数据库
生产环境请取消注释并配置真实数据库连接
"""
from typing import AsyncGenerator, Optional

# 是否使用 Mock 模式
USE_MOCK_DB = True

# 声明基类 (Mock 模式也需要保留接口)
Base = None
engine = None
async_session_factory = None

if not USE_MOCK_DB:
    # 真实数据库配置 (生产环境使用)
    from sqlalchemy.ext.asyncio import (
        AsyncSession, 
        AsyncEngine,
        create_async_engine,
        async_sessionmaker
    )
    from sqlalchemy.orm import declarative_base
    from app.core.config import settings

    engine = create_async_engine(
        settings.async_database_url,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

    async_session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    Base = declarative_base()


async def get_async_session():
    """
    获取异步数据库会话
    用于 FastAPI 依赖注入
    
    Mock 模式下返回 None
    """
    if USE_MOCK_DB:
        yield None
        return
        
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    初始化数据库（创建表）
    
    Mock 模式下为空操作
    """
    if USE_MOCK_DB:
        print("📦 数据库使用 Mock 模式 - 跳过初始化")
        return
        
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    关闭数据库连接
    
    Mock 模式下为空操作
    """
    if USE_MOCK_DB:
        print("📦 数据库 Mock 模式 - 无需关闭连接")
        return
        
    await engine.dispose()
