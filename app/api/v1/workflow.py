"""
工作流 API 接口模块
提供启动、查看状态、恢复运行等核心接口

LangGraph 1.0+ 语法：使用 Command 模式恢复中断的工作流
"""
import uuid
from typing import Optional, Dict, Any, List, Literal
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from langgraph.types import Command
import psycopg

from app.graph.workflow import get_graph
from app.graph.state import INITIAL_STATE
from app.graph.utils import get_checkpointer
from app.core.config import settings

router = APIRouter(prefix="/workflow", tags=["Workflow"])


# ============== 请求/响应模型 ==============

class NodeMetricInfo(BaseModel):
    """节点执行指标"""
    node_name: str = Field(..., description="节点名称")
    duration_ms: float = Field(default=0, description="执行耗时(毫秒)")
    input_tokens: int = Field(default=0, description="输入token数量")
    output_tokens: int = Field(default=0, description="输出token数量")
    total_tokens: int = Field(default=0, description="总token数量")
    start_time: str = Field(default="", description="开始时间")
    end_time: str = Field(default="", description="结束时间")
    model: str = Field(default="", description="使用的模型")


class StartWorkflowRequest(BaseModel):
    """启动工作流请求"""
    topic_direction: str = Field(
        ..., 
        description="主题方向，例如：AI技术、Python开发",
        min_length=1,
        max_length=200
    )


class StartWorkflowResponse(BaseModel):
    """启动工作流响应"""
    thread_id: str = Field(..., description="工作流线程ID")
    status: str = Field(..., description="当前状态")
    generated_topics: List[str] = Field(default=[], description="生成的选题列表")
    message: str = Field(..., description="提示信息")
    interrupt_info: Optional[Dict[str, Any]] = Field(default=None, description="中断信息")
    node_metrics: List[NodeMetricInfo] = Field(default=[], description="节点执行指标")


class WorkflowStateResponse(BaseModel):
    """工作流状态响应"""
    thread_id: str = Field(..., description="工作流线程ID")
    status: str = Field(..., description="当前状态")
    values: Dict[str, Any] = Field(default={}, description="当前状态值")
    next_nodes: List[str] = Field(default=[], description="下一个待执行节点")
    is_completed: bool = Field(default=False, description="是否已完成")
    interrupt_info: Optional[Dict[str, Any]] = Field(default=None, description="中断信息")
    node_metrics: List[NodeMetricInfo] = Field(default=[], description="节点执行指标")


class ResumeWorkflowRequest(BaseModel):
    """恢复工作流请求"""
    action: Literal["select_topic", "approve", "reject"] = Field(
        ..., 
        description="操作类型：select_topic(选择选题)、approve(通过审核)、reject(驳回)"
    )
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="操作数据，select_topic时需要selected_topic，reject时需要feedback"
    )


class ResumeWorkflowResponse(BaseModel):
    """恢复工作流响应"""
    thread_id: str = Field(..., description="工作流线程ID")
    status: str = Field(..., description="当前状态")
    message: str = Field(..., description="提示信息")
    next_nodes: List[str] = Field(default=[], description="下一个待执行节点")
    is_completed: bool = Field(default=False, description="是否已完成")
    result: Optional[Dict[str, Any]] = Field(default=None, description="完成时的结果")
    interrupt_info: Optional[Dict[str, Any]] = Field(default=None, description="下一个中断信息")
    node_metrics: List[NodeMetricInfo] = Field(default=[], description="节点执行指标")


class ThreadInfo(BaseModel):
    """线程信息"""
    thread_id: str = Field(..., description="线程ID")
    topic_direction: str = Field(default="", description="主题方向")
    selected_topic: str = Field(default="", description="选中的选题")
    status: str = Field(default="", description="当前状态")
    is_completed: bool = Field(default=False, description="是否已完成")
    created_at: Optional[str] = Field(default=None, description="创建时间")


class ThreadListResponse(BaseModel):
    """线程列表响应"""
    threads: List[ThreadInfo] = Field(default=[], description="线程列表")
    total: int = Field(default=0, description="总数")


# ============== 辅助函数 ==============

def extract_interrupt_info(state_snapshot) -> Optional[Dict[str, Any]]:
    """
    从状态快照中提取中断信息
    
    LangGraph 1.0+ 的中断信息存储在 tasks 中
    """
    if not state_snapshot or not hasattr(state_snapshot, 'tasks'):
        return None
    
    for task in state_snapshot.tasks:
        if hasattr(task, 'interrupts') and task.interrupts:
            for interrupt_obj in task.interrupts:
                if hasattr(interrupt_obj, 'value'):
                    return interrupt_obj.value
    
    return None


# ============== API 接口 ==============

@router.post("/start", response_model=StartWorkflowResponse)
async def start_workflow(request: StartWorkflowRequest) -> StartWorkflowResponse:
    """
    启动新的工作流
    
    接收主题方向，启动工作流并运行到第一个中断点（选题阶段）
    
    Args:
        request: 包含 topic_direction 的请求体
        
    Returns:
        包含 thread_id 和生成的选题列表
    """
    try:
        # 生成唯一的线程 ID
        thread_id = str(uuid.uuid4())
        
        # 获取编译后的图
        graph = await get_graph()
        
        # 配置
        config = {"configurable": {"thread_id": thread_id}}
        
        # 初始输入
        initial_input = {
            **INITIAL_STATE,
            "topic_direction": request.topic_direction,
            "status": "started",
        }
        
        # 运行图直到第一个中断点
        # LangGraph 1.0+ 中 ainvoke 会在遇到 interrupt() 时暂停
        result = await graph.ainvoke(initial_input, config)
        
        # 获取状态快照以获取中断信息
        state_snapshot = await graph.aget_state(config)
        interrupt_info = extract_interrupt_info(state_snapshot)
        
        # 获取生成的选题
        generated_topics = result.get("generated_topics", [])
        current_status = result.get("status", "unknown")
        node_metrics = result.get("node_metrics", [])
        
        return StartWorkflowResponse(
            thread_id=thread_id,
            status=current_status,
            generated_topics=generated_topics,
            message="工作流已启动，请选择一个选题继续",
            interrupt_info=interrupt_info,
            node_metrics=node_metrics
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动工作流失败: {str(e)}"
        )


@router.get("/state/{thread_id}", response_model=WorkflowStateResponse)
async def get_workflow_state(thread_id: str) -> WorkflowStateResponse:
    """
    获取工作流当前状态
    
    Args:
        thread_id: 工作流线程ID
        
    Returns:
        当前工作流状态快照
    """
    try:
        # 获取编译后的图
        graph = await get_graph()
        
        # 配置
        config = {"configurable": {"thread_id": thread_id}}
        
        # 获取状态快照
        state_snapshot = await graph.aget_state(config)
        
        if state_snapshot is None or state_snapshot.values is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到工作流: {thread_id}"
            )
        
        # 获取下一个待执行节点
        next_nodes = list(state_snapshot.next) if state_snapshot.next else []
        
        # 判断是否已完成
        is_completed = len(next_nodes) == 0 and not extract_interrupt_info(state_snapshot)
        
        # 获取中断信息
        interrupt_info = extract_interrupt_info(state_snapshot)
        
        # 获取节点指标
        node_metrics = state_snapshot.values.get("node_metrics", [])
        
        return WorkflowStateResponse(
            thread_id=thread_id,
            status=state_snapshot.values.get("status", "unknown"),
            values=dict(state_snapshot.values),
            next_nodes=next_nodes,
            is_completed=is_completed,
            interrupt_info=interrupt_info,
            node_metrics=node_metrics
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取工作流状态失败: {str(e)}"
        )


@router.post("/resume/{thread_id}", response_model=ResumeWorkflowResponse)
async def resume_workflow(
    thread_id: str, 
    request: ResumeWorkflowRequest
) -> ResumeWorkflowResponse:
    """
    恢复工作流运行 (LangGraph 1.0+ Command 模式)
    
    使用 Command 对象向中断的工作流提供用户输入并恢复执行
    
    Args:
        thread_id: 工作流线程ID
        request: 包含操作类型和数据的请求体
        
    Returns:
        恢复后的工作流状态
    """
    try:
        # 获取编译后的图
        graph = await get_graph()
        
        # 配置
        config = {"configurable": {"thread_id": thread_id}}
        
        # 获取当前状态
        current_state = await graph.aget_state(config)
        
        if current_state is None or current_state.values is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到工作流: {thread_id}"
            )
        
        # 根据操作类型构建 resume 数据
        # LangGraph 1.0+ 使用 Command(resume=value) 来恢复中断
        resume_value: Dict[str, Any] = {}
        
        if request.action == "select_topic":
            # 选择选题
            if not request.data or "selected_topic" not in request.data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="选择选题需要提供 selected_topic"
                )
            resume_value = {
                "selected_topic": request.data["selected_topic"],
            }
            
        elif request.action == "approve":
            # 审核通过
            resume_value = {
                "action": "approve",
            }
            
        elif request.action == "reject":
            # 审核驳回
            feedback = request.data.get("feedback", "") if request.data else ""
            resume_value = {
                "action": "reject",
                "feedback": feedback,
            }
        
        # 使用 Command 恢复工作流
        # LangGraph 1.0+ 中，使用 ainvoke(Command(resume=value), config) 恢复
        resume_command = Command(resume=resume_value)
        
        # 恢复运行直到下一个中断点或结束
        result = await graph.ainvoke(resume_command, config)
        
        # 获取更新后的状态
        updated_state = await graph.aget_state(config)
        next_nodes = list(updated_state.next) if updated_state.next else []
        interrupt_info = extract_interrupt_info(updated_state)
        is_completed = len(next_nodes) == 0 and not interrupt_info
        
        # 获取节点指标
        node_metrics = updated_state.values.get("node_metrics", [])
        
        # 构建响应
        message = "操作成功"
        final_result = None
        
        if is_completed:
            message = "工作流已完成"
            final_result = {
                "article_content": updated_state.values.get("article_content", ""),
                "visual_points": updated_state.values.get("visual_points", []),
                "image_urls": updated_state.values.get("image_urls", []),
            }
        elif interrupt_info:
            action_required = interrupt_info.get("action_required", "")
            if action_required == "review":
                message = "文章草稿已生成，请审核"
            elif action_required == "select_topic":
                message = "请选择选题"
            else:
                message = "等待用户操作"
        
        return ResumeWorkflowResponse(
            thread_id=thread_id,
            status=updated_state.values.get("status", "unknown"),
            message=message,
            next_nodes=next_nodes,
            is_completed=is_completed,
            result=final_result,
            interrupt_info=interrupt_info,
            node_metrics=node_metrics
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"恢复工作流失败: {str(e)}"
        )


@router.get("/history/{thread_id}")
async def get_workflow_history(thread_id: str) -> Dict[str, Any]:
    """
    获取工作流的历史状态记录
    
    Args:
        thread_id: 工作流线程ID
        
    Returns:
        历史状态列表
    """
    try:
        # 获取编译后的图
        graph = await get_graph()
        
        # 配置
        config = {"configurable": {"thread_id": thread_id}}
        
        # 获取历史状态
        history = []
        async for state in graph.aget_state_history(config):
            history.append({
                "config": state.config,
                "values": dict(state.values) if state.values else {},
                "next": list(state.next) if state.next else [],
                "created_at": state.created_at if hasattr(state, "created_at") else None,
            })
        
        return {
            "thread_id": thread_id,
            "history": history[:20],  # 限制返回最近 20 条
            "total": len(history)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取工作流历史失败: {str(e)}"
        )


@router.get("/threads", response_model=ThreadListResponse)
async def get_all_threads() -> ThreadListResponse:
    """
    获取所有工作流线程列表
    
    Returns:
        线程列表，包含每个线程的基本信息
    """
    try:
        threads = []
        
        # 从 PostgreSQL 数据库查询
        async with await psycopg.AsyncConnection.connect(
            settings.postgres_uri,
            autocommit=True
        ) as conn:
            async with conn.cursor() as cur:
                # 查询所有唯一的 thread_id
                await cur.execute("""
                    SELECT DISTINCT thread_id 
                    FROM checkpoints 
                    ORDER BY thread_id
                """)
                rows = await cur.fetchall()
                
                graph = await get_graph()
                
                for row in rows:
                    thread_id = row[0]
                    config = {"configurable": {"thread_id": thread_id}}
                    try:
                        state_snapshot = await graph.aget_state(config)
                        if state_snapshot and state_snapshot.values:
                            values = state_snapshot.values
                            next_nodes = list(state_snapshot.next) if state_snapshot.next else []
                            interrupt_info = extract_interrupt_info(state_snapshot)
                            is_completed = len(next_nodes) == 0 and not interrupt_info
                            
                            # 获取创建时间
                            created_at = None
                            if hasattr(state_snapshot, 'created_at') and state_snapshot.created_at:
                                created_at = state_snapshot.created_at
                            
                            threads.append(ThreadInfo(
                                thread_id=thread_id,
                                topic_direction=values.get("topic_direction", ""),
                                selected_topic=values.get("selected_topic", ""),
                                status=values.get("status", "unknown"),
                                is_completed=is_completed,
                                created_at=created_at
                            ))
                    except Exception:
                        continue
        
        return ThreadListResponse(
            threads=threads,
            total=len(threads)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取线程列表失败: {str(e)}"
        )


@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str) -> Dict[str, Any]:
    """
    删除指定的工作流线程
    
    Args:
        thread_id: 工作流线程ID
        
    Returns:
        删除结果
    """
    try:
        # 从 PostgreSQL 数据库删除
        async with await psycopg.AsyncConnection.connect(
            settings.postgres_uri,
            autocommit=True
        ) as conn:
            async with conn.cursor() as cur:
                # 删除相关记录
                await cur.execute(
                    "DELETE FROM checkpoint_writes WHERE thread_id = %s",
                    (thread_id,)
                )
                await cur.execute(
                    "DELETE FROM checkpoint_blobs WHERE thread_id = %s",
                    (thread_id,)
                )
                await cur.execute(
                    "DELETE FROM checkpoints WHERE thread_id = %s",
                    (thread_id,)
                )
                
                return {"success": True, "message": f"线程 {thread_id} 已删除"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除线程失败: {str(e)}"
        )
