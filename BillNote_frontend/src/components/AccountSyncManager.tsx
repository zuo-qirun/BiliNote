import { useEffect, useMemo, useRef, useState } from 'react'
import { getCurrentAccount, getSyncedTasks, putSyncedTasks, type CloudTask } from '@/services/account'
import { useAuthStore } from '@/store/authStore'
import { useTaskStore, type AudioMeta, type Task, type TaskStatus, type Transcript } from '@/store/taskStore'

const emptyAudioMeta = (): AudioMeta => ({
  cover_url: '',
  duration: 0,
  file_path: '',
  platform: '',
  raw_info: null,
  title: '',
  video_id: '',
})

const emptyTranscript = (): Transcript => ({
  full_text: '',
  language: '',
  raw: null,
  segments: [],
})

const toMillis = (value: string | number | undefined, fallback = Date.now()) => {
  if (typeof value === 'number') return value
  if (value) {
    const parsed = Date.parse(value)
    if (!Number.isNaN(parsed)) return parsed
  }
  return fallback
}

export const taskToCloud = (task: Task): CloudTask => ({
  task_id: task.id,
  video_url: task.formData?.video_url || '',
  platform: task.audioMeta?.platform || task.formData?.platform || '',
  status: task.status === 'FAILD' ? 'FAILED' : task.status,
  title: task.audioMeta?.title || '',
  created_at: toMillis(task.createdAt),
  updated_at: toMillis(task.updatedAt, toMillis(task.createdAt)),
  result: {
    markdown: Array.isArray(task.markdown)
      ? task.markdown[0]?.content || ''
      : task.markdown,
    transcript: task.transcript,
    audio_meta: task.audioMeta,
  },
  form_data: task.formData as unknown as Record<string, unknown>,
})

export const cloudToTask = (task: CloudTask): Task => {
  const result = task.result || {}
  const audioMeta = (result.audio_meta || emptyAudioMeta()) as AudioMeta
  const transcript = (result.transcript || emptyTranscript()) as Transcript
  const formData = {
    video_url: task.video_url || '',
    platform: task.platform || audioMeta.platform || '',
    quality: 'fast',
    model_name: '',
    provider_id: '',
    link: false,
    screenshot: false,
    ...(task.form_data || {}),
  } as Task['formData']

  return {
    id: task.task_id,
    markdown: (result.markdown || '') as Task['markdown'],
    transcript,
    status: task.status as TaskStatus,
    audioMeta: {
      ...emptyAudioMeta(),
      ...audioMeta,
      title: audioMeta.title || task.title || '',
      platform: audioMeta.platform || task.platform || '',
    },
    createdAt: new Date(task.created_at || Date.now()).toISOString(),
    updatedAt: new Date(task.updated_at || task.created_at || Date.now()).toISOString(),
    formData,
  }
}

const mergeCloudTasks = (local: CloudTask[], remote: CloudTask[]) => {
  const merged = new Map<string, CloudTask>()
  for (const task of [...local, ...remote]) {
    const previous = merged.get(task.task_id)
    if (!previous || task.updated_at >= previous.updated_at) {
      merged.set(task.task_id, task)
    }
  }
  return [...merged.values()].sort((a, b) => b.updated_at - a.updated_at)
}

export default function AccountSyncManager() {
  const token = useAuthStore(state => state.token)
  const clearSession = useAuthStore(state => state.clearSession)
  const setSession = useAuthStore(state => state.setSession)
  const tasks = useTaskStore(state => state.tasks)
  const replaceTasks = useTaskStore(state => state.replaceTasks)
  const [hydrated, setHydrated] = useState(useTaskStore.persist.hasHydrated())
  const applyingRemote = useRef(false)
  const localCloudTasks = useMemo(() => tasks.map(taskToCloud), [tasks])

  useEffect(() => {
    if (hydrated) return
    return useTaskStore.persist.onFinishHydration(() => setHydrated(true))
  }, [hydrated])

  useEffect(() => {
    if (!token || !hydrated) return
    let active = true

    const pullAndMerge = async () => {
      try {
        const user = await getCurrentAccount()
        setSession(token, user)
        const { tasks: remote } = await getSyncedTasks()
        if (!active) return
        const local = useTaskStore.getState().tasks.map(taskToCloud)
        const merged = mergeCloudTasks(local, remote)
        applyingRemote.current = true
        replaceTasks(merged.map(cloudToTask))
        await putSyncedTasks(merged)
      } catch (error: any) {
        if (error?.detail?.includes('登录') || error?.status === 401) {
          clearSession()
        }
      } finally {
        applyingRemote.current = false
      }
    }

    pullAndMerge()
    const timer = window.setInterval(pullAndMerge, 30_000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [token, hydrated, replaceTasks, clearSession, setSession])

  useEffect(() => {
    if (!token || !hydrated || applyingRemote.current) return
    const timer = window.setTimeout(() => {
      putSyncedTasks(localCloudTasks).catch(() => undefined)
    }, 1200)
    return () => window.clearTimeout(timer)
  }, [token, hydrated, localCloudTasks])

  return null
}
