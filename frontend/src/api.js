import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000 // 2分钟超时，因为 AI 生成需要时间
})

// 启动工作流
export async function startWorkflow(topicDirection) {
  const res = await api.post('/workflow/start', {
    topic_direction: topicDirection
  })
  return res.data
}

// 获取工作流状态
export async function getWorkflowState(threadId) {
  const res = await api.get(`/workflow/state/${threadId}`)
  return res.data
}

// 恢复工作流 - 选择选题
export async function selectTopic(threadId, selectedTopic) {
  const res = await api.post(`/workflow/resume/${threadId}`, {
    action: 'select_topic',
    data: { selected_topic: selectedTopic }
  })
  return res.data
}

// 恢复工作流 - 审核通过
export async function approveArticle(threadId) {
  const res = await api.post(`/workflow/resume/${threadId}`, {
    action: 'approve'
  })
  return res.data
}

// 恢复工作流 - 审核驳回
export async function rejectArticle(threadId, feedback) {
  const res = await api.post(`/workflow/resume/${threadId}`, {
    action: 'reject',
    data: { feedback }
  })
  return res.data
}

// 获取工作流历史
export async function getWorkflowHistory(threadId) {
  const res = await api.get(`/workflow/history/${threadId}`)
  return res.data
}

// 获取所有工作流线程列表
export async function getAllThreads() {
  const res = await api.get('/workflow/threads')
  return res.data
}

// 删除工作流线程
export async function deleteThread(threadId) {
  const res = await api.delete(`/workflow/threads/${threadId}`)
  return res.data
}

// ============== 流式 API (使用 LangGraph 官方 graph.astream) ==============

/**
 * 通用 SSE 事件处理器
 * @param {Response} response - fetch 响应对象
 * @param {Object} callbacks - 回调函数对象
 * @param {Function} callbacks.onInit - 初始化事件 (thread_id)
 * @param {Function} callbacks.onStart - 开始事件
 * @param {Function} callbacks.onUpdate - 节点更新事件 (node, output)
 * @param {Function} callbacks.onLlmToken - LLM token 事件 (content) - events模式
 * @param {Function} callbacks.onNodeStart - 节点开始事件 - events模式
 * @param {Function} callbacks.onNodeEnd - 节点结束事件 - events模式
 * @param {Function} callbacks.onDone - 完成事件 (finalState)
 * @param {Function} callbacks.onError - 错误事件 (message)
 */
async function handleSSEStream(response, callbacks) {
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const event = JSON.parse(line.slice(6))
          const { type, data } = event
          
          switch (type) {
            case 'init':
              callbacks.onInit?.(data)
              break
            case 'start':
              callbacks.onStart?.(data)
              break
            case 'update':
              callbacks.onUpdate?.(data.node, data.output)
              break
            case 'state':
              callbacks.onState?.(data)
              break
            case 'message':
              callbacks.onMessage?.(data)
              break
            case 'node_start':
              callbacks.onNodeStart?.(data)
              break
            case 'node_end':
              callbacks.onNodeEnd?.(data)
              break
            case 'llm_start':
              callbacks.onLlmStart?.(data)
              break
            case 'llm_token':
              callbacks.onLlmToken?.(data.content)
              break
            case 'llm_end':
              callbacks.onLlmEnd?.(data)
              break
            case 'resume':
              callbacks.onResume?.(data)
              break
            case 'done':
              callbacks.onDone?.(data)
              break
            case 'error':
              callbacks.onError?.(data.message)
              break
            default:
              console.log('未知事件类型:', type, data)
          }
        } catch (e) {
          console.error('解析SSE数据失败:', e, line)
        }
      }
    }
  }
}

/**
 * 流式启动工作流 (使用 LangGraph 官方 graph.astream)
 * @param {string} topicDirection - 主题方向
 * @param {Object} callbacks - 回调函数对象
 * @param {string} streamMode - 流式输出模式: values, updates, messages, events
 */
export function streamStartWorkflow(topicDirection, callbacks, streamMode = 'events') {
  return fetch('/api/v1/workflow/stream/start', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      topic_direction: topicDirection,
      stream_mode: streamMode
    })
  }).then(response => handleSSEStream(response, callbacks))
}

/**
 * 流式恢复工作流 - 选择选题
 * @param {string} threadId - 线程ID
 * @param {string} selectedTopic - 选中的选题
 * @param {Object} callbacks - 回调函数对象
 * @param {string} streamMode - 流式输出模式
 */
export function streamSelectTopic(threadId, selectedTopic, callbacks, streamMode = 'events') {
  return fetch(`/api/v1/workflow/stream/resume/${threadId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      action: 'select_topic',
      data: { selected_topic: selectedTopic },
      stream_mode: streamMode
    })
  }).then(response => handleSSEStream(response, callbacks))
}

/**
 * 流式恢复工作流 - 审核通过
 * @param {string} threadId - 线程ID
 * @param {Object} callbacks - 回调函数对象
 * @param {string} streamMode - 流式输出模式
 */
export function streamApproveArticle(threadId, callbacks, streamMode = 'events') {
  return fetch(`/api/v1/workflow/stream/resume/${threadId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      action: 'approve',
      stream_mode: streamMode
    })
  }).then(response => handleSSEStream(response, callbacks))
}

/**
 * 流式恢复工作流 - 审核驳回
 * @param {string} threadId - 线程ID
 * @param {string} feedback - 修改意见
 * @param {Object} callbacks - 回调函数对象
 * @param {string} streamMode - 流式输出模式
 */
export function streamRejectArticle(threadId, feedback, callbacks, streamMode = 'events') {
  return fetch(`/api/v1/workflow/stream/resume/${threadId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      action: 'reject',
      data: { feedback: feedback || '' },
      stream_mode: streamMode
    })
  }).then(response => handleSSEStream(response, callbacks))
}
