import { AlertTriangle, CheckCircle2, ChevronDown, Clipboard, X } from 'lucide-react'
import toast from 'react-hot-toast'

export interface ErrorDiagnostic {
  code: string
  title: string
  summary: string
  possible_causes: string[]
  suggestions: string[]
  retryable: boolean
  technical_message: string
}

const defaultDiagnostic = (message: string): ErrorDiagnostic => ({
  code: 'UI-UNKNOWN-001',
  title: '操作未能完成',
  summary: message || '发生了未预期的错误。',
  possible_causes: ['服务返回了非预期结果', '当前页面状态或网络连接发生变化'],
  suggestions: ['稍后重试一次', '若持续出现，请复制错误代码并联系管理员'],
  retryable: true,
  technical_message: message || 'Unknown error',
})

export function normalizeErrorDiagnostic(error: any, fallback = '操作失败'): ErrorDiagnostic {
  const remote = error?.data?.error_detail || error?.error_detail
  if (remote?.code && remote?.title) return remote

  const message = String(error?.detail || error?.msg || error?.message || fallback)
  const raw = message.toLowerCase()
  const status = Number(error?.status || error?.statusCode || error?.code)

  if (error?.code === 'ERR_CANCELED' || raw.includes('cancel')) {
    return {
      code: 'UI-REQUEST-CANCELLED', title: '操作已取消', summary: message,
      possible_causes: ['用户主动取消了操作', '页面切换导致请求中止'],
      suggestions: ['需要时可重新发起操作'], retryable: true, technical_message: message,
    }
  }
  if (error?.code === 'ECONNABORTED' || raw.includes('timeout') || raw.includes('超时')) {
    return {
      code: 'UI-NET-TIMEOUT', title: '请求响应超时', summary: '服务器未能在规定时间内返回结果。',
      possible_causes: ['网络速度较慢或不稳定', '服务器或上游服务正在处理耗时任务'],
      suggestions: ['保持网络连接并重试', '大文件上传时请保持页面打开'], retryable: true, technical_message: message,
    }
  }
  if (status === -1 || raw.includes('network') || raw.includes('网络')) {
    return {
      code: 'UI-NET-OFFLINE', title: '无法连接到服务器', summary: '浏览器没有收到服务器响应。',
      possible_causes: ['当前设备网络中断', '域名、反向代理或后端服务暂时不可用', '请求被浏览器扩展或防火墙拦截'],
      suggestions: ['检查网络后重试', '刷新页面并查看右下角后端状态', '管理员可检查 Nginx 与容器状态'],
      retryable: true, technical_message: message,
    }
  }
  if (status === 401 || status === 403) {
    return {
      code: status === 401 ? 'UI-AUTH-401' : 'UI-AUTH-403',
      title: status === 401 ? '登录状态无效' : '当前账号没有权限', summary: message,
      possible_causes: status === 401 ? ['登录已过期', '凭据在其他设备失效'] : ['当前账号角色权限不足'],
      suggestions: status === 401 ? ['重新登录后再试'] : ['切换管理员账号或联系管理员'],
      retryable: false, technical_message: message,
    }
  }
  return defaultDiagnostic(message)
}

function DiagnosticToast({ diagnostic, toastId }: { diagnostic: ErrorDiagnostic; toastId: string }) {
  const copy = () => {
    navigator.clipboard.writeText([
      `错误代码：${diagnostic.code}`,
      `错误：${diagnostic.title}`,
      `说明：${diagnostic.summary}`,
      `技术信息：${diagnostic.technical_message}`,
    ].join('\n'))
    toast.success('诊断信息已复制')
  }

  return (
    <div className="diagnostic-toast w-[min(92vw,440px)] overflow-hidden rounded-2xl border border-red-200 bg-white shadow-[0_24px_70px_-22px_rgba(127,29,29,0.38)]">
      <div className="flex gap-3 border-b border-red-100 bg-gradient-to-r from-red-50 to-orange-50/60 p-4">
        <div className="mt-0.5 rounded-xl bg-red-600 p-2 text-white"><AlertTriangle className="h-4 w-4" /></div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <strong className="text-sm text-neutral-950">{diagnostic.title}</strong>
            <code className="rounded-md bg-red-100 px-1.5 py-0.5 text-[10px] font-bold text-red-700">{diagnostic.code}</code>
          </div>
          <p className="mt-1 text-xs leading-5 text-neutral-600">{diagnostic.summary}</p>
        </div>
        <button onClick={() => toast.dismiss(toastId)} className="h-7 rounded-lg p-1 text-neutral-400 hover:bg-white hover:text-neutral-700" aria-label="关闭">
          <X className="h-4 w-4" />
        </button>
      </div>
      <details className="group px-4 py-3">
        <summary className="flex cursor-pointer list-none items-center justify-between text-xs font-semibold text-neutral-700">
          查看原因分析与处理建议
          <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
        </summary>
        <div className="mt-3 grid gap-3 border-t border-neutral-100 pt-3 sm:grid-cols-2">
          <div>
            <div className="text-[11px] font-bold uppercase tracking-wider text-amber-700">可能原因</div>
            <ul className="mt-2 space-y-1.5 text-xs leading-5 text-neutral-600">
              {diagnostic.possible_causes.map(item => <li key={item}>• {item}</li>)}
            </ul>
          </div>
          <div>
            <div className="text-[11px] font-bold uppercase tracking-wider text-emerald-700">处理建议</div>
            <ul className="mt-2 space-y-1.5 text-xs leading-5 text-neutral-600">
              {diagnostic.suggestions.map(item => <li key={item} className="flex gap-1.5"><CheckCircle2 className="mt-1 h-3 w-3 shrink-0 text-emerald-600" />{item}</li>)}
            </ul>
          </div>
        </div>
        <button onClick={copy} className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-neutral-500 hover:text-neutral-900">
          <Clipboard className="h-3.5 w-3.5" />复制诊断信息
        </button>
      </details>
    </div>
  )
}

export function showErrorDiagnostic(error: any, fallback?: string) {
  const diagnostic = normalizeErrorDiagnostic(error, fallback)
  return toast.custom(t => <DiagnosticToast diagnostic={diagnostic} toastId={t.id} />, {
    duration: 12000,
    position: 'top-right',
  })
}

