import { create } from 'zustand'
import { persist } from 'zustand/middleware'

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

interface AuthState {
  token: string | null
  user: AccountUser | null
  setSession: (token: string, user: AccountUser) => void
  clearSession: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    set => ({
      token: null,
      user: null,
      setSession: (token, user) => set({ token, user }),
      clearSession: () => set({ token: null, user: null }),
    }),
    { name: 'bilinote-auth' }
  )
)

export const getAuthToken = () => useAuthStore.getState().token
