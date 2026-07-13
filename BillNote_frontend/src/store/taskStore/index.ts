import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { generateNote } from '@/services/note.ts'
import { v4 as uuidv4 } from 'uuid'
import toast from 'react-hot-toast'
import { get, set, del } from 'idb-keyval'
import { deleteSyncedTask } from '@/services/account'
import { getAuthToken } from '@/store/authStore'

export type TaskStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'PARSING'
  | 'DOWNLOADING'
  | 'TRANSCRIBING'
  | 'SUMMARIZING'
  | 'FORMATTING'
  | 'SAVING'
  | 'SUCCESS'
  | 'FAILED'
  | 'FAILD'

export interface AudioMeta {
  cover_url: string
  duration: number
  file_path: string
  platform: string
  raw_info: any
  title: string
  video_id: string
}

export interface Segment {
  start: number
  end: number
  text: string
}

export interface Transcript {
  full_text: string
  language: string
  raw: any
  segments: Segment[]
}

export interface Markdown {
  ver_id: string
  content: string
  style: string
  model_name: string
  created_at: string
}

export interface TaskErrorDetail {
  code: string
  title: string
  summary: string
  stage: 'unknown' | 'downloading' | 'transcribing' | 'summarizing' | string
  retryable: boolean
  possible_causes: string[]
  suggestions: string[]
  technical_message: string
}

export interface Task {
  id: string
  markdown: string | Markdown[]
  liveMarkdown?: string
  transcript: Transcript
  status: TaskStatus
  audioMeta: AudioMeta
  createdAt: string
  updatedAt?: string
  message?: string
  errorDetail?: TaskErrorDetail
  formData: {
    video_url: string
    link: undefined | boolean
    screenshot: undefined | boolean
    platform: string
    quality: string
    model_name: string
    provider_id: string
    style?: string
    extras?: string
    format?: string[]
    video_understanding?: boolean
    video_interval?: number
    grid_size?: number[]
  }
}

interface TaskStore {
  tasks: Task[]
  currentTaskId: string | null
  addPendingTask: (taskId: string, platform: string, formData: any) => void
  updateTaskContent: (id: string, data: Partial<Omit<Task, 'id' | 'createdAt'>>) => void
  removeTask: (id: string) => void
  clearTasks: () => void
  setCurrentTask: (taskId: string | null) => void
  getCurrentTask: () => Task | null
  retryTask: (id: string, payload?: any) => void
  replaceTasks: (tasks: Task[]) => void
}

const emptyTranscript: Transcript = {
  full_text: '',
  language: '',
  raw: null,
  segments: [],
}

const emptyAudioMeta: AudioMeta = {
  cover_url: '',
  duration: 0,
  file_path: '',
  platform: '',
  raw_info: null,
  title: '',
  video_id: '',
}

export const useTaskStore = create<TaskStore>()(
  persist(
    (set, get) => ({
      tasks: [],
      currentTaskId: null,

      addPendingTask: (taskId: string, platform: string, formData: any) =>
        set(state => ({
          tasks: [
            {
              formData,
              id: taskId,
              status: 'PENDING',
              markdown: '',
              liveMarkdown: '',
              message: '',
              errorDetail: undefined,
              transcript: emptyTranscript,
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
              audioMeta: {
                ...emptyAudioMeta,
                platform,
              },
            },
            ...state.tasks,
          ],
          currentTaskId: taskId,
        })),

      updateTaskContent: (id, data) =>
        set(state => ({
          tasks: state.tasks.map(task => {
            if (task.id !== id) return task
            if (task.status === 'SUCCESS' && data.status === 'SUCCESS') return task

            const nextStatus = data.status ?? task.status

            if (typeof data.markdown === 'string' && nextStatus === 'SUCCESS') {
              const prev = task.markdown
              const newVersion: Markdown = {
                ver_id: `${task.id}-${uuidv4()}`,
                content: data.markdown,
                style: task.formData.style || '',
                model_name: task.formData.model_name || '',
                created_at: new Date().toISOString(),
              }

              let updatedMarkdown: Markdown[]
              if (Array.isArray(prev)) {
                updatedMarkdown = [newVersion, ...prev]
              } else {
                updatedMarkdown = [
                  newVersion,
                  ...(typeof prev === 'string' && prev
                    ? [
                        {
                          ver_id: `${task.id}-${uuidv4()}`,
                          content: prev,
                          style: task.formData.style || '',
                          model_name: task.formData.model_name || '',
                          created_at: new Date().toISOString(),
                        },
                      ]
                    : []),
                ]
              }

              return {
                ...task,
                ...data,
                markdown: updatedMarkdown,
                liveMarkdown: '',
                updatedAt: new Date().toISOString(),
              }
            }

            return { ...task, ...data, updatedAt: new Date().toISOString() }
          }),
        })),

      getCurrentTask: () => {
        const currentTaskId = get().currentTaskId
        return get().tasks.find(task => task.id === currentTaskId) || null
      },

      retryTask: async (id: string, payload?: any) => {
        if (!id) {
          toast.error('任务不存在')
          return
        }

        const task = get().tasks.find(item => item.id === id)
        if (!task) return

        const newFormData = payload || task.formData
        try {
          await generateNote({
            ...newFormData,
            task_id: id,
          })
        } catch (e: any) {
          if (e?.data?.reason === 'transcriber_model_not_ready') {
            toast.error(
              e?.data?.downloading
                ? '转写模型正在下载中，请稍后再重试'
                : '转写模型尚未下载，请先去“设置 -> 音频转写配置”页下载',
            )
            return
          }
          console.error('重试任务失败:', e)
          return
        }

        set(state => ({
          tasks: state.tasks.map(item =>
            item.id === id
              ? {
                  ...item,
                  formData: newFormData,
                  status: 'PENDING',
                  liveMarkdown: '',
                  message: '',
                  errorDetail: undefined,
                  updatedAt: new Date().toISOString(),
                }
              : item,
          ),
        }))
      },

      removeTask: async id => {
        const task = get().tasks.find(item => item.id === id)
        if (!task) return

        if (getAuthToken()) {
          try {
            await deleteSyncedTask(id)
          } catch (error) {
            console.warn('Failed to delete synced task:', error)
            toast.error('删除失败，请检查网络连接后重试')
            return
          }
        }

        set(state => ({
          tasks: state.tasks.filter(item => item.id !== id),
          currentTaskId: state.currentTaskId === id ? null : state.currentTaskId,
        }))
        toast.success('笔记已删除')
      },

      clearTasks: () => set({ tasks: [], currentTaskId: null }),

      setCurrentTask: taskId => set({ currentTaskId: taskId }),

      replaceTasks: tasks =>
        set(state => ({
          tasks,
          currentTaskId:
            state.currentTaskId && tasks.some(task => task.id === state.currentTaskId)
              ? state.currentTaskId
              : null,
        })),
    }),
    {
      name: 'task-storage',
      storage: createJSONStorage(() => ({
        getItem: async (name: string): Promise<string | null> => {
          const value = await get(name)
          return value ?? null
        },
        setItem: async (name: string, value: string): Promise<void> => {
          await set(name, value)
        },
        removeItem: async (name: string): Promise<void> => {
          await del(name)
        },
      })),
    },
  ),
)
