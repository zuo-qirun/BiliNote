import type { ReactNode, FC } from 'react'
// import "@/global.css"
import { Toaster } from 'react-hot-toast'

interface RootLayoutProps {
  children: ReactNode
}

export const metadata = {
  title: 'BiliNote - 视频笔记生成器',
  description: '通过视频链接结合大模型自动生成对应的笔记',
}

const RootLayout: FC<RootLayoutProps> = ({ children }) => {
  return (
    <div className="app-shell min-h-screen text-neutral-900">
      <Toaster
        position="top-right"
        gutter={10}
        toastOptions={{
          style: {
            borderRadius: '14px',
            background: '#171717',
            color: '#fff',
            padding: '12px 14px',
            boxShadow: '0 20px 55px -24px rgba(15, 23, 42, .55)',
          },
        }}
      />
      {children}
    </div>
  )
}

export default RootLayout
