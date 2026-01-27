-- AI 内容运营助手 - 数据库初始化脚本
-- 用于在本地 PostgreSQL 中创建数据库

-- 创建数据库（如果不存在）
-- 注意：此命令需要在 psql 中以 postgres 用户执行
-- CREATE DATABASE aicontent;

-- 连接到 aicontent 数据库后执行以下命令

-- 启用 UUID 扩展（可选，用于生成 UUID）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- LangGraph Checkpointer 会自动创建以下表结构
-- 这里提供参考，实际由 AsyncPostgresSaver.setup() 自动创建

-- Checkpoints 表（存储图状态快照）
-- CREATE TABLE IF NOT EXISTS checkpoints (
--     thread_id TEXT NOT NULL,
--     checkpoint_ns TEXT NOT NULL DEFAULT '',
--     checkpoint_id TEXT NOT NULL,
--     parent_checkpoint_id TEXT,
--     type TEXT,
--     checkpoint JSONB NOT NULL,
--     metadata JSONB NOT NULL DEFAULT '{}',
--     created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
--     PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
-- );

-- Checkpoint Blobs 表（存储大型二进制数据）
-- CREATE TABLE IF NOT EXISTS checkpoint_blobs (
--     thread_id TEXT NOT NULL,
--     checkpoint_ns TEXT NOT NULL DEFAULT '',
--     channel TEXT NOT NULL,
--     version TEXT NOT NULL,
--     type TEXT NOT NULL,
--     blob BYTEA,
--     PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
-- );

-- Checkpoint Writes 表（存储待写入数据）
-- CREATE TABLE IF NOT EXISTS checkpoint_writes (
--     thread_id TEXT NOT NULL,
--     checkpoint_ns TEXT NOT NULL DEFAULT '',
--     checkpoint_id TEXT NOT NULL,
--     task_id TEXT NOT NULL,
--     idx INTEGER NOT NULL,
--     channel TEXT NOT NULL,
--     type TEXT,
--     blob BYTEA NOT NULL,
--     PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
-- );

-- 注意事项：
-- 1. 确保 PostgreSQL 服务正在运行
-- 2. 默认连接信息：localhost:5432
-- 3. 用户名/密码：postgres/password（请根据实际情况修改）
-- 4. 数据库名：aicontent

-- 测试连接命令：
-- psql -h localhost -U postgres -d aicontent
