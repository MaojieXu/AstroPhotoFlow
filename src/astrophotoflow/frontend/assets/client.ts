import type { ZodType } from 'zod'
import { errorSchema } from './contracts'

export type FetchApi = (path: string, init?: RequestInit) => Promise<Response>

export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly kind: 'network' | 'service' | 'contract',
    readonly status?: number,
    readonly code?: string,
    readonly requestId?: string
  ) {
    super(message)
    this.name = 'ApiClientError'
  }
}

export function createApiClient(fetchApi: FetchApi) {
  function upload(path: string, file: Blob, onProgress: (loaded: number) => void): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = new XMLHttpRequest()
      request.open('PUT', path)
      request.upload.onprogress = event => { if (event.lengthComputable) onProgress(event.loaded) }
      request.onload = () => request.status >= 200 && request.status < 300
        ? resolve()
        : reject(new ApiClientError('文件上传失败（HTTP ' + request.status + '）。', 'service', request.status))
      request.onerror = () => reject(new ApiClientError('无法连接 AstroPhotoFlow 服务。', 'network'))
      request.send(file)
    })
  }
  async function request<T>(path: string, schema: ZodType<T>, init?: RequestInit): Promise<T> {
    let response: Response
    try {
      response = await fetchApi(path, init)
    } catch (error) {
      if (error instanceof TypeError) throw new ApiClientError('无法连接 AstroPhotoFlow 服务。', 'network')
      throw error
    }

    let body: unknown
    try {
      body = await response.json()
    } catch {
      throw new ApiClientError('服务响应不是有效 JSON。', 'contract', response.status)
    }

    if (!response.ok) {
      const parsedError = errorSchema.safeParse(body)
      if (!parsedError.success) throw new ApiClientError('服务错误响应不符合接口契约。', 'contract', response.status)
      throw new ApiClientError(
        parsedError.data.error.message, 'service', response.status,
        parsedError.data.error.code, parsedError.data.request_id
      )
    }

    const parsed = schema.safeParse(body)
    if (!parsed.success) throw new ApiClientError('服务成功响应不符合接口契约。', 'contract', response.status)
    return parsed.data
  }

  async function getBlob(path: string): Promise<Blob> {
    let response: Response
    try {
      response = await fetchApi(path, {cache: 'no-store'})
    } catch (error) {
      if (error instanceof TypeError) throw new ApiClientError('无法连接 AstroPhotoFlow 服务。', 'network')
      throw error
    }
    if (!response.ok) {
      let body: unknown
      try { body = await response.json() } catch {
        throw new ApiClientError('服务响应不是有效 JSON。', 'contract', response.status)
      }
      const parsedError = errorSchema.safeParse(body)
      if (!parsedError.success) throw new ApiClientError('服务错误响应不符合接口契约。', 'contract', response.status)
      throw new ApiClientError(
        parsedError.data.error.message, 'service', response.status,
        parsedError.data.error.code, parsedError.data.request_id
      )
    }
    if (!response.headers.get('Content-Type')?.startsWith('image/jpeg')) {
      throw new ApiClientError('预览响应类型不符合接口契约。', 'contract', response.status)
    }
    return response.blob()
  }

  return {
    get: <T>(path: string, schema: ZodType<T>) => request(path, schema),
    getBlob,
    upload,
    send: <T>(path: string, schema: ZodType<T>, method: 'POST' | 'PATCH' | 'DELETE', data: unknown) =>
      request(path, schema, {
        method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
      })
  }
}
