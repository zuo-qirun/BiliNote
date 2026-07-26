import type { Platform } from './types'

// 与 backend/app/validators/video_url_validator.py 保持一致
export function detectPlatform(url: string | undefined | null): Platform | null {
  if (!url)
    return null

  let parsed: URL
  try {
    parsed = new URL(url)
  }
  catch {
    return null
  }

  const hostname = parsed.hostname.toLowerCase()
  const pathname = parsed.pathname.toLowerCase()
  const isBilibiliHost = hostname === 'bilibili.com' || hostname.endsWith('.bilibili.com')

  // B 站既有 www/m 子域的视频页，也有 b23.tv 短链。短链最终会跳转到视频页，
  // 但 popup 可能在跳转完成前打开，因此也要直接识别。
  if (hostname === 'b23.tv' || hostname === 'www.b23.tv')
    return 'bilibili'
  if (isBilibiliHost && /^\/video\/(?:bv[0-9a-z]+|av\d+)/i.test(pathname))
    return 'bilibili'

  if (/(^|\.)youtube\.com$/.test(hostname) && (/^\/watch$/.test(pathname) || pathname.startsWith('/shorts/')))
    return 'youtube'
  if (hostname === 'youtu.be' || hostname.endsWith('.youtu.be'))
    return 'youtube'
  if (hostname.includes('douyin'))
    return 'douyin'
  if (hostname.includes('kuaishou'))
    return 'kuaishou'
  return null
}

export const PLATFORM_LABELS: Record<Platform, string> = {
  bilibili: '哔哩哔哩',
  youtube: 'YouTube',
  douyin: '抖音',
  kuaishou: '快手',
  local: '本地',
}
