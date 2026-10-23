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

  return {
    get: <T>(path: string, schema: ZodType<T>) => request(path, schema),
    send: <T>(path: string, schema: ZodType<T>, method: 'POST' | 'PATCH', data: unknown) =>
      request(path, schema, {
        method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
      })
  }
}
