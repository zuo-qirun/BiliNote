import type { CloudTask, Platform, TaskRecord, TaskStatus } from './types'
import { getCurrentAccount, getSyncedTasks, putSyncedTasks } from './api'
import { authReady, authSession, tasks, tasksReady } from './storage'
import { MAX_TASKS } from './constants'

function taskToCloud(task: TaskRecord): CloudTask {
  return {
    task_id: task.taskId,
    video_url: task.videoUrl,
    platform: task.platform,
    status: task.status,
    message: task.message,
    title: task.title || task.result?.audio_meta?.title || '',
    created_at: task.createdAt,
    updated_at: task.updatedAt,
    result: task.result,
  }
}

function cloudToTask(task: CloudTask): TaskRecord {
  return {
    taskId: task.task_id,
    videoUrl: task.video_url || '',
    platform: (task.platform || 'local') as Platform,
    status: task.status as TaskStatus,
    message: task.message || '',
    title: task.title || task.result?.audio_meta?.title || '',
    createdAt: task.created_at || Date.now(),
    updatedAt: task.updated_at || task.created_at || Date.now(),
    result: task.result,
  }
}

function mergeTasks(local: CloudTask[], remote: CloudTask[]): CloudTask[] {
  const merged = new Map<string, CloudTask>()
  for (const task of [...local, ...remote]) {
    const current = merged.get(task.task_id)
    if (!current || task.updated_at >= current.updated_at)
      merged.set(task.task_id, task)
  }
  return [...merged.values()].sort((a, b) => b.updated_at - a.updated_at)
}

let syncTimer: ReturnType<typeof setTimeout> | null = null
let syncRunning = false

export async function syncTaskHistory(): Promise<void> {
  await Promise.all([authReady, tasksReady])
  if (!authSession.value?.token || syncRunning)
    return

  syncRunning = true
  try {
    const user = await getCurrentAccount()
    authSession.value = { ...authSession.value, user }
    const remote = await getSyncedTasks()
    const merged = mergeTasks((tasks.value || []).map(taskToCloud), remote)
    tasks.value = merged.slice(0, MAX_TASKS).map(cloudToTask)
    await putSyncedTasks(merged)
  }
  catch (error) {
    const message = (error as Error).message || ''
    if (message.includes('401') || message.includes('登录'))
      authSession.value = { token: '', user: null }
    throw error
  }
  finally {
    syncRunning = false
  }
}

export function scheduleTaskSync(delay = 800): void {
  if (!authSession.value?.token)
    return
  if (syncTimer)
    clearTimeout(syncTimer)
  syncTimer = setTimeout(() => {
    syncTaskHistory().catch(() => undefined)
  }, delay)
}
