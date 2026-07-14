import { useEffect, useMemo, useState } from 'react'
import { LoaderCircle, Play, Share2 } from 'lucide-react'
import { useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import gfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import rehypeSlug from 'rehype-slug'
import { toast } from 'react-hot-toast'
import { getSharedNote, SharedNote } from '@/services/note'
import { Button } from '@/components/ui/button'
import ErrorDiagnosticCard from '@/components/ErrorDiagnosticCard'
import 'github-markdown-css/github-markdown-light.css'
import 'katex/dist/katex.min.css'

const platformNames: Record<string, string> = {
  bilibili: '哔哩哔哩',
  youtube: 'YouTube',
  douyin: '抖音',
}

export default function SharePage() {
  const { shareId = '' } = useParams()
  const [note, setNote] = useState<SharedNote | null>(null)
  const [loading, setLoading] = useState(true)
  const [failure, setFailure] = useState<unknown>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setFailure(null)

    getSharedNote(shareId)
      .then(data => {
        if (active) setNote(data)
      })
      .catch(error => {
        if (active) setFailure(error)
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [shareId, attempt])

  const formattedDate = useMemo(() => {
    if (!note?.created_at) return ''
    return new Intl.DateTimeFormat('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(note.created_at))
  }, [note?.created_at])

  const copyLink = async () => {
    await navigator.clipboard.writeText(window.location.href)
    toast.success('分享链接已复制')
  }

  if (loading) {
    return (
      <main className="fixed inset-0 z-30 flex overflow-y-auto items-center justify-center bg-[#f7f7f4] text-neutral-500">
        <LoaderCircle className="mr-2 h-5 w-5 animate-spin" />
        正在打开分享笔记
      </main>
    )
  }

  if (failure || !note) {
    return (
      <main className="fixed inset-0 z-30 flex overflow-y-auto items-center justify-center bg-[radial-gradient(circle_at_top_left,#eff6ff_0,transparent_38%),#f8fafc] px-4 py-10 sm:px-8">
        <ErrorDiagnosticCard
          error={failure || { msg: '这篇笔记不存在，或分享链接不完整。', code: 404 }}
          fallback="分享链接不可用"
          onRetry={() => setAttempt(value => value + 1)}
        />
      </main>
    )
  }

  return (
    <div className="fixed inset-0 z-30 touch-pan-y overflow-x-hidden overflow-y-auto overscroll-y-contain bg-[#f7f7f4] text-neutral-900 [-webkit-overflow-scrolling:touch]">
      <header className="sticky top-0 z-20 border-b border-black/5 bg-[#f7f7f4]/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 sm:px-8 sm:py-4">
          <a href="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-pink-500 text-sm font-bold text-white shadow-sm shadow-pink-500/20">
              B
            </span>
            <span>BiliNote</span>
            <span className="hidden rounded-full border border-black/10 px-2 py-0.5 text-xs font-normal text-neutral-500 sm:inline">
              公开分享
            </span>
          </a>
          <Button onClick={copyLink} variant="outline" size="sm" className="rounded-full bg-white">
            <Share2 className="mr-1.5 h-4 w-4" />
            复制链接
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-3 py-5 sm:px-8 sm:py-10">
        <article className="overflow-hidden rounded-2xl border border-black/[0.06] bg-white shadow-[0_18px_60px_rgba(15,23,42,0.06)] sm:rounded-[28px]">
          <div className="border-b border-black/[0.06] px-5 py-7 sm:px-12 sm:py-11">
            <div className="mb-4 flex flex-wrap items-center gap-2 text-xs font-medium uppercase tracking-[0.13em] text-neutral-400">
              <span>{platformNames[note.platform || ''] || note.platform || '视频笔记'}</span>
              {formattedDate && <><span>·</span><time>{formattedDate}</time></>}
            </div>
            <h1 className="max-w-4xl text-3xl font-bold leading-tight tracking-[-0.035em] text-neutral-950 sm:text-5xl">
              {note.title || 'BiliNote 分享笔记'}
            </h1>
            <div className="mt-5 flex flex-wrap items-center gap-3 text-sm text-neutral-500">
              {note.author && <span>整理自 {note.author}</span>}
              {note.video_url && (
                <a
                  href={note.video_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 rounded-full bg-pink-50 px-3 py-1.5 font-medium text-pink-700 transition hover:bg-pink-100"
                >
                  <Play className="h-3.5 w-3.5 fill-current" />
                  查看原视频
                </a>
              )}
            </div>
          </div>

          <div className="markdown-body mx-auto max-w-none px-5 py-7 sm:px-12 sm:py-11">
            <ReactMarkdown
              remarkPlugins={[gfm, remarkMath]}
              rehypePlugins={[rehypeKatex, rehypeSlug]}
              components={{
                img: props => (
                  <img
                    {...props}
                    loading="lazy"
                    className="mx-auto my-7 max-h-[680px] rounded-xl border border-black/5 object-contain shadow-sm"
                  />
                ),
                a: props => <a {...props} target={props.href?.startsWith('http') ? '_blank' : undefined} rel="noreferrer" />,
                table: props => <div className="my-6 overflow-x-auto"><table {...props} /></div>,
              }}
            >
              {note.markdown}
            </ReactMarkdown>
          </div>
        </article>
        <footer className="py-8 text-center text-xs text-neutral-400">
          由 BiliNote 生成并分享
        </footer>
      </main>
    </div>
  )
}
