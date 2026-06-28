import { useEffect, useState } from 'react'
import { LoaderCircle, ShieldCheck, UsersRound } from 'lucide-react'
import toast from 'react-hot-toast'
import { listAccounts, updateAccountRole, type AccountUser } from '@/services/account'

type ManagedUser = AccountUser & { id: number; created_at: number }

export default function AdminUsers() {
  const [users, setUsers] = useState<ManagedUser[]>([])
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState<number | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      setUsers((await listAccounts()).users)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load().catch(() => toast.error('用户列表加载失败'))
  }, [])

  const changeRole = async (user: ManagedUser, role: AccountUser['role']) => {
    setUpdating(user.id)
    try {
      const updated = await updateAccountRole(user.id, role)
      setUsers(current => current.map(item => item.id === user.id ? { ...item, ...updated } : item))
      toast.success(`${user.username} 已设为 ${updated.role_label}`)
    } finally {
      setUpdating(null)
    }
  }

  return (
    <div className="h-full overflow-auto p-5 md:p-8">
      <div className="mx-auto max-w-5xl">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-neutral-950 text-white">
            <UsersRound className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-neutral-950">用户与权限</h1>
            <p className="text-sm text-neutral-500">管理免费用户、特权用户和管理员的生成额度。</p>
          </div>
        </div>

        <div className="overflow-hidden rounded-2xl border bg-white">
          {loading ? (
            <div className="flex h-40 items-center justify-center text-neutral-400">
              <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />加载中
            </div>
          ) : (
            <div className="divide-y">
              {users.map(user => (
                <div key={user.id} className="grid gap-3 p-4 sm:grid-cols-[1fr_1fr_auto] sm:items-center">
                  <div>
                    <div className="font-medium text-neutral-900">{user.username}</div>
                    <div className="mt-1 text-xs text-neutral-500">{user.email || '旧账号未填写邮箱'}</div>
                  </div>
                  <div className="text-xs text-neutral-500">
                    今日已生成 {user.quota.used} 篇
                    {user.quota.limit != null && ` / ${user.quota.limit} 篇`}
                  </div>
                  <label className="flex items-center gap-2">
                    <ShieldCheck className="h-4 w-4 text-neutral-400" />
                    <select
                      value={user.role}
                      disabled={updating === user.id}
                      onChange={event => changeRole(user, event.target.value as AccountUser['role'])}
                      className="rounded-lg border bg-white px-3 py-2 text-sm"
                    >
                      <option value="free">免费用户 · 5篇/天</option>
                      <option value="privileged">特权用户 · 50篇/天</option>
                      <option value="admin">管理员 · 无限制</option>
                    </select>
                  </label>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
