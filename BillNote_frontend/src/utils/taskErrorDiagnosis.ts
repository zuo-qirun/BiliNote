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

  if (
    normalized.includes('转写器')
    || normalized.includes('b站asr')
    || normalized.includes('快手asr')
    || normalized.includes('备用转写器')
    || normalized.includes('fast-whisper')
  ) {
    return {
      code: 'TRANSCRIBER-ALL-FAILED',
      title: '音频转写未能完成',
      summary: '视频没有字幕属于正常情况；本次是在自动回退到音频转写后，所有可用转写器均未得到有效文本。',
      stage: 'transcribing',
      retryable: true,
      possible_causes: [
        '视频源未提供字幕，系统已正常改走音频转写',
        'Bcut 返回空文本或上游转写任务暂时失败',
        '备用转写服务不可用，或本地 Whisper 模型尚未下载完成',
      ],
      suggestions: [
        '稍后重试，外部转写服务可能会恢复',
        '管理员可在转写设置确认 fast-whisper 模型已下载',
        '若音频本身无对白、静音或背景声过强，建议换用带字幕的视频源',
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
