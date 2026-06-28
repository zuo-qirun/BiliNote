import request from '@/utils/request'

export interface AccountUser {
  username: string
  email?: string | null
  phone?: string | null
  role: 'free' | 'privileged' | 'admin'
  role_label: string
  quota: {
    limit: number | null
    used: number
    remaining: number | null
    period: 'day' | 'lifetime'
    period_key: string
  }
}

export interface AuthResult {
  token: string
  user: AccountUser
}

export interface CloudTask {
  task_id: string
  video_url: string
  platform: string
  status: string
  message?: string
  title?: string
  created_at: number
  updated_at: number
  result?: {
    markdown?: unknown
    transcript?: unknown
    audio_meta?: unknown
  }
  form_data?: Record<string, unknown>
}

export interface CaptchaResult {
  captcha_id: string
  image: string
  expires_in: number
}

export const getCaptcha = () =>
  request.get<any, CaptchaResult>('/auth/captcha', { suppressToast: true })

export const registerAccount = (data: {
  username: string
  password: string
  email: string
  phone?: string
  captcha_id: string
  captcha_code: string
}) => request.post<any, AuthResult>('/auth/register', data)

export const loginAccount = (username: string, password: string) =>
  request.post<any, AuthResult>('/auth/login', { username, password })

export const logoutAccount = () =>
  request.post('/auth/logout', undefined, { suppressToast: true })

export const getCurrentAccount = () =>
  request.get<any, AccountUser>('/auth/me', { suppressToast: true })

export const listAccounts = () =>
  request.get<any, { users: Array<AccountUser & { id: number; created_at: number }> }>('/admin/users')

export const updateAccountRole = (userId: number, role: AccountUser['role']) =>
  request.patch<any, AccountUser>(`/admin/users/${userId}/role`, { role })

export const getSyncedTasks = () =>
  request.get<any, { tasks: CloudTask[] }>('/sync/tasks', { suppressToast: true })

export const putSyncedTasks = (tasks: CloudTask[]) =>
  request.post('/sync/tasks', { tasks }, { suppressToast: true })

export const deleteSyncedTask = (taskId: string) =>
  request.delete(`/sync/tasks/${encodeURIComponent(taskId)}`, { suppressToast: true })
