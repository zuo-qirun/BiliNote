import { Download } from 'lucide-react'

export default function ExtensionDownloadButton({ compact = false }: { compact?: boolean }) {
  return (
    <a
      href="/downloads/BiliNote-extension-v2.zip"
      download
      title="下载 BiliNote 浏览器插件（MIT 开源）"
      aria-label="下载 BiliNote 浏览器插件"
      className="flex h-10 items-center justify-center gap-2 rounded-xl px-2.5 text-neutral-500 transition-colors hover:bg-neutral-100 hover:text-neutral-900"
    >
      <Download className="h-5 w-5" />
      {!compact && <span className="text-sm">下载插件</span>}
    </a>
  )
}
