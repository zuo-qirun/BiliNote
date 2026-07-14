import request from '@/utils/request'

export interface UploadResult {
  url: string
  filename: string
  original_filename: string
  size: number
}

interface UploadOptions {
  signal?: AbortSignal
  onProgress?: (loaded: number, total: number) => void
}

export const uploadFile = (file: File, options: UploadOptions = {}) => {
  const formData = new FormData()
  formData.append('file', file)

  return request.post<any, UploadResult>('/upload', formData, {
    // Video uploads must not inherit the global ten-second API timeout.
    timeout: 30 * 60 * 1000,
    suppressToast: true,
    signal: options.signal,
    onUploadProgress: event => {
      options.onProgress?.(event.loaded, event.total || file.size)
    },
  })
}
