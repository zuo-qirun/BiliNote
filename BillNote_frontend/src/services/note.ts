import request from '@/utils/request'
import toast from 'react-hot-toast'

export interface ShareNotePayload {
  markdown: string
  title?: string
  task_id?: string
  video_url?: string
  platform?: string
  author?: string
}

export interface SharedNote extends ShareNotePayload {
  share_id: string
  created_at: string
}

export interface ShareNoteResult {
  share_id: string
  path: string
}

export const shareNote = (data: ShareNotePayload) =>
  request.post<any, ShareNoteResult>('/share_note', data)

export const getSharedNote = (shareId: string) =>
  request.get<any, SharedNote>(`/shared_note/${encodeURIComponent(shareId)}`, { suppressToast: true })

export const generateNote = async (data: {
  video_url: string
  platform: string
  quality: string
  model_name: string
  provider_id: string
  task_id?: string
  format: Array<string>
  style: string
  extras?: string
  video_understand?: boolean
  video_interval?: number
  grid_size: Array<number>
}) => {
  try {
    console.log('generateNote', data)
    const response = await request.post('/generate_note', data)

    if (!response) {
      toast.error('笔记生成任务提交失败')
      return null
    }

    toast.success('笔记生成任务已提交')
    return response
  } catch (e: any) {
    console.error('请求出错', e)
    throw e
  }
}

export const delete_task = async ({ video_id, platform }) => {
  try {
    const data = {
      video_id,
      platform,
    }
    const res = await request.post('/delete_task', data)
    toast.success('任务已成功删除')
    return res
  } catch (e) {
    console.error('删除任务失败:', e)
    throw e
  }
}

export const get_task_status = async (task_id: string) => {
  try {
    return await request.get('/task_status/' + task_id, { suppressToast: true })
  } catch (e) {
    console.error('轮询任务状态失败', e)
    throw e
  }
}

export const confirmEmptyTranscript = (taskId: string, isNormal: boolean) =>
  request.post(`/task_confirm_empty_transcript/${encodeURIComponent(taskId)}`, {
    is_normal: isNormal,
  })
