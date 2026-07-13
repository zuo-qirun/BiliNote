import { useMemo, useState } from 'react'
import {
  AlertTriangle,
  Check,
  ChevronDown,
  CircleDotDashed,
  Clipboard,
  Lightbulb,
  RotateCcw,
  ShieldAlert,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { Task } from '@/store/taskStore'
import { diagnoseTaskError } from '@/utils/taskErrorDiagnosis'

const stageLabels: Record<string, string> = {
  unknown: '处理阶段未知',
  downloading: '下载视频或音频',
  transcribing: '音频转写',
  summarizing: 'AI 生成笔记',
}

interface TaskErrorPanelProps {
  task: Task
  onRetry: () => void
}

export function TaskErrorPanel({ task, onRetry }: TaskErrorPanelProps) {
  const detail = useMemo(() => diagnoseTaskError(task), [task])
  const [copied, setCopied] = useState(false)
  const stageLabel = stageLabels[detail.stage] || detail.stage

  const copyDiagnostics = async () => {
    const report = [
      `任务 ID：${task.id}`,
      `错误代码：${detail.code}`,
      `失败阶段：${stageLabel}`,
      `模型：${task.formData?.model_name || '未知'}`,
      `供应商：${task.formData?.provider_id || '未知'}`,
      `视频：${task.formData?.video_url || '未知'}`,
      `技术信息：${detail.technical_message}`,
    ].join('\n')
    await navigator.clipboard.writeText(report)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1800)
  }

  return (
    <ScrollArea className="h-full min-h-0 w-full touch-pan-y overscroll-y-contain">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-5 sm:px-6 sm:py-8">
        <section className="overflow-hidden rounded-2xl border border-red-200/80 bg-white shadow-[0_18px_55px_-38px_rgba(185,28,28,0.55)]">
          <div className="relative border-b border-red-100 bg-[linear-gradient(135deg,#fff8f7_0%,#fff_58%,#fff4ed_100%)] px-5 py-5 sm:px-7">
            <div className="absolute top-0 right-0 h-28 w-28 translate-x-8 -translate-y-8 rounded-full border-[18px] border-red-100/50" />
            <div className="relative flex items-start gap-3.5">
              <div className="mt-0.5 rounded-xl bg-red-600 p-2.5 text-white shadow-sm">
                <ShieldAlert className="h-5 w-5" aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-red-100 px-2.5 py-1 text-[11px] font-semibold tracking-wide text-red-700">
                    {detail.code}
                  </span>
                  <span className="inline-flex items-center gap-1 rounded-full border border-neutral-200 bg-white/80 px-2.5 py-1 text-[11px] text-neutral-600">
                    <CircleDotDashed className="h-3 w-3" /> {stageLabel}
                  </span>
                </div>
                <h2 className="text-xl font-bold tracking-tight text-neutral-950 sm:text-2xl">{detail.title}</h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-neutral-600">{detail.summary}</p>
              </div>
            </div>
          </div>

          <div className="grid gap-0 md:grid-cols-2">
            <div className="border-b border-neutral-100 p-5 md:border-r md:border-b-0 sm:p-6">
              <h3 className="flex items-center gap-2 text-sm font-bold text-neutral-900">
                <AlertTriangle className="h-4 w-4 text-amber-600" /> 可能的原因
              </h3>
              <ol className="mt-4 space-y-3">
                {detail.possible_causes.map((cause, index) => (
                  <li key={cause} className="flex gap-3 text-sm leading-5 text-neutral-600">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-amber-50 text-[11px] font-bold text-amber-700">
                      {index + 1}
                    </span>
                    <span>{cause}</span>
                  </li>
                ))}
              </ol>
            </div>

            <div className="p-5 sm:p-6">
              <h3 className="flex items-center gap-2 text-sm font-bold text-neutral-900">
                <Lightbulb className="h-4 w-4 text-emerald-600" /> 建议处理方式
              </h3>
              <ul className="mt-4 space-y-3">
                {detail.suggestions.map(suggestion => (
                  <li key={suggestion} className="flex gap-3 text-sm leading-5 text-neutral-600">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                    <span>{suggestion}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <details className="group rounded-xl border border-neutral-200 bg-neutral-50/80 px-4 py-3">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium text-neutral-700">
            <span>技术信息（提供给管理员）</span>
            <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
          </summary>
          <div className="mt-3 border-t border-neutral-200 pt-3">
            <dl className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-x-3 gap-y-2 text-xs leading-5">
              <dt className="text-neutral-500">任务 ID</dt><dd className="break-all font-mono text-neutral-700">{task.id}</dd>
              <dt className="text-neutral-500">模型</dt><dd className="break-all font-mono text-neutral-700">{task.formData?.model_name || '未知'}</dd>
              <dt className="text-neutral-500">供应商</dt><dd className="break-all font-mono text-neutral-700">{task.formData?.provider_id || '未知'}</dd>
              <dt className="text-neutral-500">原始错误</dt><dd className="break-words font-mono text-red-700">{detail.technical_message}</dd>
            </dl>
          </div>
        </details>

        <div className="flex flex-col-reverse gap-2 pb-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={copyDiagnostics} className="gap-2">
            {copied ? <Check className="h-4 w-4" /> : <Clipboard className="h-4 w-4" />}
            {copied ? '已复制诊断信息' : '复制诊断信息'}
          </Button>
          <Button onClick={onRetry} className="gap-2 bg-neutral-950 text-white hover:bg-neutral-800">
            <RotateCcw className="h-4 w-4" /> 重试当前任务
          </Button>
        </div>
      </div>
    </ScrollArea>
  )
}
