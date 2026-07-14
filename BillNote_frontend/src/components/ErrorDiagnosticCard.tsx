import { AlertTriangle, CheckCircle2, Clipboard } from 'lucide-react'
import toast from 'react-hot-toast'
import { normalizeErrorDiagnostic } from '@/utils/errorDiagnostics'

interface ErrorDiagnosticCardProps {
  error: unknown
  fallback?: string
  onRetry?: () => void
}

export default function ErrorDiagnosticCard({ error, fallback, onRetry }: ErrorDiagnosticCardProps) {
  const diagnostic = normalizeErrorDiagnostic(error, fallback)

  const copyDetails = async () => {
    await navigator.clipboard.writeText([
      `错误代码：${diagnostic.code}`,
      `错误：${diagnostic.title}`,
      `说明：${diagnostic.summary}`,
      `技术信息：${diagnostic.technical_message}`,
    ].join('\n'))
    toast.success('诊断信息已复制')
  }

  return (
    <section className="w-full max-w-2xl overflow-hidden rounded-[28px] border border-red-200/80 bg-white text-left shadow-[0_28px_90px_-35px_rgba(127,29,29,.35)]">
      <div className="flex gap-4 border-b border-red-100 bg-gradient-to-br from-red-50 via-white to-amber-50/70 p-6 sm:p-8">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-red-600 text-white shadow-lg shadow-red-600/20">
          <AlertTriangle className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-950 sm:text-2xl">{diagnostic.title}</h1>
            <code className="rounded-lg bg-red-100 px-2 py-1 text-[11px] font-bold text-red-700">{diagnostic.code}</code>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">{diagnostic.summary}</p>
        </div>
      </div>
      <div className="grid gap-6 p-6 sm:grid-cols-2 sm:p-8">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-[.14em] text-amber-700">可能原因</h2>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
            {diagnostic.possible_causes.map(item => <li key={item}>• {item}</li>)}
          </ul>
        </div>
        <div>
          <h2 className="text-xs font-bold uppercase tracking-[.14em] text-emerald-700">处理建议</h2>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
            {diagnostic.suggestions.map(item => (
              <li key={item} className="flex gap-2">
                <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-emerald-600" />{item}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t border-slate-100 px-6 py-4 sm:px-8">
        {onRetry && diagnostic.retryable && (
          <button type="button" onClick={onRetry} className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800">重新尝试</button>
        )}
        <button type="button" onClick={copyDetails} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-50 hover:text-slate-950">
          <Clipboard className="h-4 w-4" />复制诊断信息
        </button>
        <a href="/" className="ml-auto text-sm font-semibold text-blue-600 hover:text-blue-700">返回首页</a>
      </div>
    </section>
  )
}
