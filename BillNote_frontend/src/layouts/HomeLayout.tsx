import React, { FC, useEffect, useRef, useState } from 'react'
import {
  BookOpenText,
  History as HistoryIcon,
  PanelLeftClose,
  PanelLeftOpen,
  SlidersHorizontal,
  SquarePen,
} from 'lucide-react'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip.tsx'

import { Link } from 'react-router-dom'
import { ResizablePanel, ResizablePanelGroup, ResizableHandle } from '@/components/ui/resizable'
import { ScrollArea } from "@/components/ui/scroll-area.tsx"
import type { ImperativePanelHandle } from 'react-resizable-panels'
import logo from '@/assets/icon.svg'
import { cn } from '@/lib/utils'
import { useTaskStore } from '@/store/taskStore'
import AccountButton from '@/components/AccountButton'
import ExtensionDownloadButton from '@/components/ExtensionDownloadButton'
import { useAuthStore } from '@/store/authStore'

interface IProps {
  NoteForm: React.ReactNode
  Preview: React.ReactNode
  History: React.ReactNode
}

const HomeLayout: FC<IProps> = ({ NoteForm, Preview, History }) => {
  const [, setShowSettings] = useState(false)
  const [isLeftCollapsed, setIsLeftCollapsed] = useState(false)
  const [isMiddleCollapsed, setIsMiddleCollapsed] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const [mobileView, setMobileView] = useState<'form' | 'preview' | 'history'>('form')
  const currentTaskId = useTaskStore(state => state.currentTaskId)
  const previousTaskIdRef = useRef(currentTaskId)
  const isAdmin = useAuthStore(state => state.user?.role === 'admin')
  const leftPanelRef = useRef<ImperativePanelHandle>(null)
  const middlePanelRef = useRef<ImperativePanelHandle>(null)

  useEffect(() => {
    const media = window.matchMedia('(max-width: 767px)')
    const sync = () => setIsMobile(media.matches)
    sync()
    media.addEventListener('change', sync)
    return () => media.removeEventListener('change', sync)
  }, [])

  useEffect(() => {
    const taskChanged = previousTaskIdRef.current !== currentTaskId
    previousTaskIdRef.current = currentTaskId

    if (isMobile && taskChanged && currentTaskId) {
      setMobileView('preview')
    }
  }, [currentTaskId, isMobile])

  if (isMobile) {
    const mobileTabs = [
      { id: 'form' as const, label: '创建', icon: SquarePen },
      { id: 'preview' as const, label: '笔记', icon: BookOpenText },
      { id: 'history' as const, label: '历史', icon: HistoryIcon },
    ]

    return (
      <div className="flex h-[100dvh] flex-col overflow-hidden bg-slate-50">
        <header className="workspace-header flex h-16 shrink-0 items-center justify-between px-4 shadow-[0_8px_30px_-26px_rgba(15,23,42,.5)]">
          <div className="flex items-center gap-2.5">
            <div className="h-10 w-10 overflow-hidden rounded-2xl border border-blue-100 bg-blue-50 p-0.5 shadow-sm">
              <img src={logo} alt="BiliNote" className="h-full w-full object-contain" />
            </div>
            <div>
              <div className="text-lg font-extrabold leading-none tracking-[-0.03em] text-slate-950">BiliNote</div>
              <div className="mt-1 text-[10px] font-medium tracking-[0.12em] text-slate-400">视频知识工作台</div>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <ExtensionDownloadButton compact />
            <AccountButton compact />
            {isAdmin && (
              <Link
                to="/settings"
                aria-label="打开设置"
                className="flex h-10 w-10 items-center justify-center rounded-xl text-neutral-500 transition-colors active:bg-neutral-100"
              >
                <SlidersHorizontal className="h-5 w-5" />
              </Link>
            )}
          </div>
        </header>

        <section className="min-h-0 flex-1 overflow-hidden">
          {mobileView === 'form' && (
            <ScrollArea className="h-full">
              <div className="mx-auto w-full max-w-xl p-4 pb-8">{NoteForm}</div>
            </ScrollArea>
          )}
          {mobileView === 'preview' && (
            <main className="h-full overflow-hidden bg-white">{Preview}</main>
          )}
          {mobileView === 'history' && (
            <div className="h-full overflow-hidden bg-white">{History}</div>
          )}
        </section>

        <nav
          className="grid shrink-0 grid-cols-3 border-t border-slate-200/80 bg-white/92 px-2 pt-1 shadow-[0_-12px_35px_-28px_rgba(15,23,42,.5)] backdrop-blur-xl"
          style={{ paddingBottom: 'max(0.35rem, env(safe-area-inset-bottom))' }}
          aria-label="手机端主导航"
        >
          {mobileTabs.map(({ id, label, icon: Icon }) => {
            const active = mobileView === id
            return (
              <button
                key={id}
                type="button"
                onClick={() => setMobileView(id)}
                className={cn(
                  'relative flex min-h-14 flex-col items-center justify-center gap-1 rounded-xl text-[11px] font-medium transition-colors',
                  active ? 'text-primary' : 'text-neutral-400 active:bg-neutral-50'
                )}
              >
                {active && <span className="absolute top-0 h-0.5 w-8 rounded-full bg-primary" />}
                <Icon className="h-5 w-5" strokeWidth={active ? 2.3 : 1.8} />
                <span>{label}</span>
              </button>
            )
          })}
        </nav>
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-100/80 p-2">
      <ResizablePanelGroup direction="horizontal" className="h-full w-full">
        {/* 左边表单 */}
        <ResizablePanel
          ref={leftPanelRef}
          defaultSize={23}
          minSize={10}
          maxSize={35}
          collapsible
          collapsedSize={0}
          onCollapse={() => setIsLeftCollapsed(true)}
          onExpand={() => setIsLeftCollapsed(false)}
        >
          <aside className="workspace-panel flex h-full flex-col overflow-hidden rounded-l-2xl border shadow-[0_20px_60px_-45px_rgba(15,23,42,.5)]">
            <header className="workspace-header flex h-18 items-center justify-between px-5">
              <div className="flex items-center gap-2">
                <div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-2xl border border-blue-100 bg-blue-50 shadow-sm">
                  <img src={logo} alt="logo" className="h-full w-full object-contain" />
                </div>
                <div><div className="text-xl font-extrabold tracking-[-0.035em] text-slate-950">BiliNote</div><div className="text-[10px] font-medium tracking-[.12em] text-slate-400">KNOWLEDGE STUDIO</div></div>
              </div>
              <div className="flex items-center gap-1">
                <ExtensionDownloadButton compact />
                <AccountButton compact />
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        onClick={() => leftPanelRef.current?.collapse()}
                        className="text-muted-foreground hover:text-primary cursor-pointer rounded p-1 hover:bg-neutral-100"
                      >
                        <PanelLeftClose className="h-5 w-5" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <span>收起工作区</span>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                {isAdmin && (
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger onClick={() => setShowSettings(true)}>
                        <Link to={'/settings'}>
                          <SlidersHorizontal className="text-muted-foreground hover:text-primary cursor-pointer" />
                        </Link>
                      </TooltipTrigger>
                      <TooltipContent>
                        <span>全局配置</span>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                )}
              </div>
            </header>
            <ScrollArea className="flex-1 overflow-auto">
              <div className="p-4 pb-8">{NoteForm}</div>
            </ScrollArea>
          </aside>
        </ResizablePanel>

        <ResizableHandle />

        {/* 左面板折叠时的展开按钮 */}
        {isLeftCollapsed && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => leftPanelRef.current?.expand()}
                  className="flex h-full w-8 shrink-0 items-center justify-center border-r border-neutral-200 bg-white hover:bg-neutral-50"
                >
                  <PanelLeftOpen className="h-4 w-4 text-muted-foreground" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">
                <span>展开工作区</span>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}

        {/* 中间历史 */}
        <ResizablePanel
          ref={middlePanelRef}
          defaultSize={16}
          minSize={10}
          maxSize={30}
          collapsible
          collapsedSize={0}
          onCollapse={() => setIsMiddleCollapsed(true)}
          onExpand={() => setIsMiddleCollapsed(false)}
        >
          <aside className="workspace-panel flex h-full flex-col overflow-hidden border-y border-slate-200/80">
            <header className="workspace-header flex h-12 shrink-0 items-center justify-between px-4">
              <span className="text-xs font-bold uppercase tracking-[.14em] text-slate-500">生成历史</span>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      onClick={() => middlePanelRef.current?.collapse()}
                      className="text-muted-foreground hover:text-primary cursor-pointer rounded p-1 hover:bg-neutral-100"
                    >
                      <PanelLeftClose className="h-4 w-4" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <span>收起历史</span>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </header>
            <ScrollArea className="flex-1 overflow-auto">
              <div>{History}</div>
            </ScrollArea>
          </aside>
        </ResizablePanel>

        <ResizableHandle />

        {/* 中间面板折叠时的展开按钮 */}
        {isMiddleCollapsed && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => middlePanelRef.current?.expand()}
                  className="flex h-full w-8 shrink-0 items-center justify-center border-r border-neutral-200 bg-white hover:bg-neutral-50"
                >
                  <HistoryIcon className="h-4 w-4 text-muted-foreground" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">
                <span>展开历史</span>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}

        {/* 右边预览 */}
        <ResizablePanel defaultSize={61} minSize={30}>
          <main className="flex h-full flex-col overflow-hidden rounded-r-2xl border border-slate-200/80 bg-white p-3 shadow-[0_20px_60px_-45px_rgba(15,23,42,.5)]">{Preview}</main>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  )
}

export default HomeLayout
