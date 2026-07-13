import { useEffect, useRef } from 'react'
import toast from 'react-hot-toast'
import { useTaskStore } from '@/store/taskStore'
import { get_task_status } from '@/services/note.ts'

export const useTaskPolling = (interval = 3000) => {
  const tasks = useTaskStore(state => state.tasks)
  const updateTaskContent = useTaskStore(state => state.updateTaskContent)
  const tasksRef = useRef(tasks)

  useEffect(() => {
    tasksRef.current = tasks
  }, [tasks])

  useEffect(() => {
    const timer = setInterval(async () => {
      const pendingTasks = tasksRef.current.filter(
        task => task.status !== 'SUCCESS' && task.status !== 'FAILED',
      )

      if (pendingTasks.length === 0) return

      for (const task of pendingTasks) {
        try {
          const res = await get_task_status(task.id)
          const status = res?.status
          const partial = res?.partial_result || {}

          const patch: Record<string, any> = {}
          if (status) patch.status = status
          if (typeof res?.message === 'string') patch.message = res.message
          if (typeof partial?.markdown === 'string') patch.liveMarkdown = partial.markdown
          if (partial?.transcript) patch.transcript = partial.transcript
          if (partial?.audio_meta) patch.audioMeta = partial.audio_meta

          if (status === 'SUCCESS') {
            const { markdown, transcript, audio_meta } = res.result
            toast.success('笔记生成成功')
            updateTaskContent(task.id, {
              status,
              markdown,
              liveMarkdown: '',
              message: res?.message || '',
              transcript,
              audioMeta: audio_meta,
            })
            continue
          }

          if (status === 'FAILED') {
            updateTaskContent(task.id, {
              status,
              message: res?.message || '任务失败',
              errorDetail: res?.error_detail,
            })
            console.warn(`Task ${task.id} failed`)
            continue
          }

          if (Object.keys(patch).length > 0) {
            updateTaskContent(task.id, patch)
          }
        } catch (e: any) {
          console.error('轮询任务失败:', e)
          const message = e?.data?.message || e?.msg || '任务失败'
          updateTaskContent(task.id, {
            status: 'FAILED',
            message,
            errorDetail: e?.data?.error_detail,
          })
        }
      }
    }, interval)

    return () => clearInterval(timer)
  }, [interval, updateTaskContent])
}
