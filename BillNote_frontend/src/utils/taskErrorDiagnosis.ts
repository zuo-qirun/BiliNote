import type { Task, TaskErrorDetail } from '@/store/taskStore'

export function diagnoseTaskError(task: Task): TaskErrorDetail {
  if (task.errorDetail) return task.errorDetail

  const technicalMessage = task.message?.trim() || '任务执行失败，后端未返回具体错误。'
  const normalized = technicalMessage.toLowerCase()

  if (normalized.includes('your request was blocked') || normalized.includes('403')) {
    return {
      code: 'AI_PROVIDER_BLOCKED',
      title: 'AI 服务拒绝了请求',
      summary: '视频解析和转写可能已经完成，但 AI 模型供应商拒绝继续生成笔记。',
      stage: 'summarizing',
      retryable: false,
      possible_causes: [
        'API Key 已失效、被冻结，或没有所选模型的调用权限',
        '第三方代理限制了服务器 IP、地区、账户或请求来源',
        '代理服务的风控、防火墙或内容策略拦截了请求',
        '供应商账户余额、套餐或并发权限异常',
      ],
      suggestions: [
        '在模型设置中测试当前供应商连接',
        '检查 API Key、账户状态和所选模型权限',
        '更换可用的 API 地址、Key 或模型供应商后重试',
      ],
      technical_message: technicalMessage,
    }
  }

  return {
    code: 'TASK_EXECUTION_FAILED',
    title: '任务执行失败',
    summary: '任务处理过程中遇到异常，暂时无法完成笔记生成。',
    stage: task.transcript?.segments?.length ? 'summarizing' : 'unknown',
    retryable: true,
    possible_causes: ['上游服务临时异常或网络连接中断', '当前模型、转写器或视频源返回了非预期结果'],
    suggestions: ['稍后重试当前任务', '若持续失败，请复制技术信息并交给管理员排查'],
    technical_message: technicalMessage,
  }
}
