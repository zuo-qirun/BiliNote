import { createApp } from 'vue'
import App from './views/App.vue'
import { setupApp } from '~/logic/common-setup'
import { detectPlatform } from '~/logic/platform'

// B 站是 SPA：从首页/搜索页点进视频时，document 不会重载。需要在 URL 变化后
// 重新挂载或卸载悬浮按钮，避免视频页未识别、非视频页残留按钮。
let mountedUrl = ''
let mountedContainer: HTMLElement | null = null
let mountedApp: ReturnType<typeof createApp> | null = null

function unmount() {
  mountedApp?.unmount()
  mountedContainer?.remove()
  mountedApp = null
  mountedContainer = null
  mountedUrl = ''
}

function refresh() {
  const currentUrl = window.location.href
  if (currentUrl === mountedUrl)
    return

  unmount()
  if (!detectPlatform(currentUrl) || !document.body)
    return

  const container = document.createElement('div')
  container.id = __NAME__
  const root = document.createElement('div')
  const styleEl = document.createElement('link')
  const shadowDOM = container.attachShadow?.({ mode: __DEV__ ? 'open' : 'closed' }) || container
  styleEl.setAttribute('rel', 'stylesheet')
  styleEl.setAttribute('href', browser.runtime.getURL('dist/contentScripts/style.css'))
  shadowDOM.appendChild(styleEl)
  shadowDOM.appendChild(root)
  document.body.appendChild(container)
  const app = createApp(App)
  setupApp(app)
  app.mount(root)
  mountedContainer = container
  mountedApp = app
  mountedUrl = currentUrl
}

function notifyUrlChange() {
  window.dispatchEvent(new Event('bilinote:urlchange'))
}

for (const method of ['pushState', 'replaceState'] as const) {
  const original = history[method]
  history[method] = function (...args) {
    const result = original.apply(this, args)
    notifyUrlChange()
    return result
  }
}

window.addEventListener('popstate', notifyUrlChange)
window.addEventListener('bilinote:urlchange', refresh)
refresh()
