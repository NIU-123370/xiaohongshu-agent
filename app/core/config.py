"""
应用配置模块
使用 pydantic-settings 管理环境变量
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # 应用配置
    app_name: str = "AI内容运营助手"
    debug: bool = True
    
    # 数据库配置 (SQLAlchemy AsyncIO)
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/aicontent"
    
    # PostgreSQL 连接配置 (psycopg3 / LangGraph Checkpointer)
    postgres_uri: str = "postgresql://postgres:password@localhost:5432/aicontent"
    
    @property
    def async_database_url(self) -> str:
        """获取异步数据库 URL"""
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()
