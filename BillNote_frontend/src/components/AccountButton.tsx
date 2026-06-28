import { FormEvent, useEffect, useState } from 'react'
import { Cloud, LoaderCircle, LogOut, RefreshCw, ShieldCheck, UserRound } from 'lucide-react'
import toast from 'react-hot-toast'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getCaptcha, loginAccount, logoutAccount, registerAccount } from '@/services/account'
import { useAuthStore } from '@/store/authStore'

export default function AccountButton({ compact = false }: { compact?: boolean }) {
  const token = useAuthStore(state => state.token)
  const user = useAuthStore(state => state.user)
  const setSession = useAuthStore(state => state.setSession)
  const clearSession = useAuthStore(state => state.clearSession)
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [captchaId, setCaptchaId] = useState('')
  const [captchaImage, setCaptchaImage] = useState('')
  const [captchaCode, setCaptchaCode] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const refreshCaptcha = async () => {
    const result = await getCaptcha()
    setCaptchaId(result.captcha_id)
    setCaptchaImage(result.image)
    setCaptchaCode('')
  }

  useEffect(() => {
    if (open && !token && mode === 'register' && !captchaId) {
      refreshCaptcha().catch(() => toast.error('验证码加载失败'))
    }
  }, [open, token, mode, captchaId])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    try {
      const result =
        mode === 'login'
          ? await loginAccount(username.trim(), password)
          : await registerAccount({
              username: username.trim(),
              password,
              email: email.trim(),
              phone: phone.trim() || undefined,
              captcha_id: captchaId,
              captcha_code: captchaCode.trim(),
            })
      setSession(result.token, result.user)
      setPassword('')
      setOpen(false)
      toast.success(mode === 'login' ? '登录成功，正在同步历史' : '账号已创建，正在同步历史')
    } catch (error: any) {
      toast.error(error?.detail || error?.msg || '登录失败')
      if (mode === 'register') refreshCaptcha().catch(() => undefined)
    } finally {
      setSubmitting(false)
    }
  }

  const logout = async () => {
    await logoutAccount().catch(() => undefined)
    clearSession()
    setOpen(false)
    toast.success('已退出账号，本地历史仍保留')
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          type="button"
          aria-label={token ? `账号：${user?.username}` : '登录账号'}
          className="flex h-10 items-center justify-center gap-2 rounded-xl px-2.5 text-neutral-500 transition-colors hover:bg-neutral-100 hover:text-neutral-900"
        >
          <span className="relative">
            <UserRound className="h-5 w-5" />
            {token && <span className="absolute -right-1 -bottom-1 h-2 w-2 rounded-full bg-emerald-500 ring-2 ring-white" />}
          </span>
          {!compact && <span className="max-w-24 truncate text-sm">{user?.username || '登录'}</span>}
        </button>
      </DialogTrigger>

      <DialogContent className="overflow-hidden border-0 p-0 shadow-2xl sm:max-w-md">
        <div className="bg-neutral-950 px-6 py-6 text-white">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl bg-white/10">
            <Cloud className="h-5 w-5 text-pink-300" />
          </div>
          <DialogHeader>
            <DialogTitle className="text-xl text-white">
              {token ? 'BiliNote 云端账号' : mode === 'login' ? '登录 BiliNote' : '创建 BiliNote 账号'}
            </DialogTitle>
            <DialogDescription className="text-neutral-400">
              {token
                ? '生成历史会在网页、其他设备和浏览器插件之间自动同步。'
                : '登录后，所有设备共享生成历史；模型密钥不会上传到账号历史。'}
            </DialogDescription>
          </DialogHeader>
        </div>

        {token ? (
          <div className="space-y-5 p-6">
            <div className="flex items-center justify-between rounded-2xl border bg-neutral-50 p-4">
              <div>
                <div className="text-xs text-neutral-400">当前账号</div>
                <div className="mt-1 font-semibold text-neutral-900">{user?.username}</div>
                <div className="mt-1 text-xs text-neutral-500">{user?.role_label}</div>
              </div>
              <div className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">自动同步</div>
            </div>
            <div className="rounded-2xl border border-amber-100 bg-amber-50/70 p-4">
              <div className="flex items-center gap-2 text-sm font-medium text-amber-950">
                <ShieldCheck className="h-4 w-4" />
                今日生成额度
              </div>
              <div className="mt-2 text-2xl font-semibold text-amber-950">
                {user?.quota.limit == null
                  ? '无限制'
                  : `${user?.quota.remaining ?? 0} / ${user?.quota.limit}`}
              </div>
              {user?.quota.limit != null && (
                <div className="mt-1 text-xs text-amber-800">已使用 {user?.quota.used ?? 0} 篇，北京时间每日重置</div>
              )}
            </div>
            <Button variant="outline" className="w-full" onClick={logout}>
              <LogOut className="mr-2 h-4 w-4" />
              退出账号
            </Button>
          </div>
        ) : (
          <form className="space-y-4 p-6" onSubmit={submit}>
            <div className="grid grid-cols-2 rounded-xl bg-neutral-100 p-1 text-sm">
              <button
                type="button"
                onClick={() => setMode('login')}
                className={`rounded-lg px-3 py-2 ${mode === 'login' ? 'bg-white font-medium shadow-sm' : 'text-neutral-500'}`}
              >
                登录
              </button>
              <button
                type="button"
                onClick={() => {
                  setMode('register')
                  setCaptchaId('')
                }}
                className={`rounded-lg px-3 py-2 ${mode === 'register' ? 'bg-white font-medium shadow-sm' : 'text-neutral-500'}`}
              >
                注册
              </button>
            </div>
            <Input
              value={username}
              onChange={event => setUsername(event.target.value)}
              placeholder="账号（3-32 位字母或数字）"
              autoComplete="username"
              required
              minLength={3}
              maxLength={32}
            />
            <Input
              value={password}
              onChange={event => setPassword(event.target.value)}
              placeholder="密码（至少 8 位）"
              type="password"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              required
              minLength={8}
              maxLength={128}
            />
            {mode === 'register' && (
              <>
                <Input
                  value={email}
                  onChange={event => setEmail(event.target.value)}
                  placeholder="邮箱（必填）"
                  type="email"
                  autoComplete="email"
                  required
                  maxLength={254}
                />
                <Input
                  value={phone}
                  onChange={event => setPhone(event.target.value)}
                  placeholder="手机号（选填）"
                  type="tel"
                  autoComplete="tel"
                  maxLength={30}
                />
                <div className="flex gap-2">
                  <Input
                    value={captchaCode}
                    onChange={event => setCaptchaCode(event.target.value.toUpperCase())}
                    placeholder="图形验证码"
                    required
                    minLength={4}
                    maxLength={10}
                  />
                  <button
                    type="button"
                    title="刷新验证码"
                    className="flex h-10 min-w-36 items-center justify-center overflow-hidden rounded-md border bg-stone-50"
                    onClick={() => refreshCaptcha().catch(() => toast.error('验证码加载失败'))}
                  >
                    {captchaImage
                      ? <img src={captchaImage} alt="图形验证码" className="h-full w-auto" />
                      : <RefreshCw className="h-4 w-4 animate-spin" />}
                  </button>
                </div>
                <p className="text-xs leading-5 text-neutral-500">
                  新账号默认为免费用户，每日可生成 5 篇；特权用户每日 50 篇。
                </p>
              </>
            )}
            <Button className="w-full" disabled={submitting}>
              {submitting && <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />}
              {mode === 'login' ? '登录并同步历史' : '注册并同步历史'}
            </Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
