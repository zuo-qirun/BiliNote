import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip.tsx'
import { Link, Outlet } from 'react-router-dom'
import { SlidersHorizontal } from 'lucide-react'
import React from 'react'
import logo from '@/assets/icon.svg'

interface ISettingLayoutProps {
  Menu: React.ReactNode
}
const SettingLayout = ({ Menu }: ISettingLayoutProps) => {
  return (
    <div className="h-full w-full bg-slate-100 p-2">
      <div className="flex h-[calc(100dvh-1rem)] flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-[0_24px_70px_-48px_rgba(15,23,42,.55)] md:flex-row">
        {/* 左侧部分：Header + 表单 */}
        <aside className="flex max-h-[46dvh] w-full shrink-0 flex-col border-b border-slate-200 bg-gradient-to-b from-white to-slate-50/70 md:max-h-none md:w-[300px] md:border-r md:border-b-0">
          {/* Header */}
          <header className="flex h-14 shrink-0 items-center justify-between px-4 md:h-16 md:px-6">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center overflow-hidden rounded-xl md:h-10 md:w-10 md:rounded-2xl">
                <img src={logo} alt="logo" className="h-full w-full object-contain" />
              </div>
              <div><div className="text-xl font-extrabold tracking-[-.035em] text-slate-950">BiliNote</div><div className="text-[10px] font-medium tracking-[.12em] text-slate-400">ADMIN CONSOLE</div></div>
            </div>
            <div>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <Link to={'/'}>
                      <SlidersHorizontal className="text-muted-foreground hover:text-primary cursor-pointer" />
                    </Link>
                  </TooltipTrigger>
                  <TooltipContent>
                    <span>返回首页</span>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </header>

          {/* 表单内容 */}
          <div className="flex-1 overflow-auto p-3 md:p-4">
            {/*<NoteForm />*/}
            {Menu}
          </div>
        </aside>

        {/* 右侧预览区域 */}
        <main className="min-h-0 flex-1 overflow-auto bg-slate-50/55 md:h-full md:overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
export default SettingLayout
