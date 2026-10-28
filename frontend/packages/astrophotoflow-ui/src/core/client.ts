import type { ZodType, z } from 'zod'
import {
  configStateSchema,
  directorySelectionSchema,
  errorSchema,
  workbenchResultSchema
} from './contracts'
import type { ConfigSave, ConfigState, WorkbenchResult } from './contracts'

export type FetchApi = (path: string, init?: RequestInit) => Promise<Response>

export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly kind: 'network' | 'service' | 'contract',
    readonly status?: number,
    readonly code?: string,
    readonly requestId?: string,
    readonly fields?: z.infer<typeof errorSchema>['error']['fields']
  ) {
    super(message)
    this.name = 'ApiClientError'
  }
}

export function createApiClient(fetchApi: FetchApi) {
  function upload(
    path: string,
    file: Blob,
    onProgress: (loaded: number) => void
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = new XMLHttpRequest()
      request.open('PUT', path)
      request.upload.onprogress = (event) => {
        if (event.lengthComputable) onProgress(event.loaded)
      }
      request.onload = () =>
        request.status >= 200 && request.status < 300
          ? resolve()
          : reject(
              new ApiClientError(
                '文件上传失败（HTTP ' + request.status + '）。',
                'service',
                request.status
              )
            )
      request.onerror = () =>
        reject(new ApiClientError('无法连接 AstroPhotoFlow 服务。', 'network'))
      request.send(file)
    })
  }
  async function request<T>(
    path: string,
    schema: ZodType<T>,
    init?: RequestInit
  ): Promise<T> {
    let response: Response
    try {
      response = await fetchApi(path, init)
    } catch (error) {
      if (error instanceof TypeError)
        throw new ApiClientError('无法连接 AstroPhotoFlow 服务。', 'network')
      throw error
    }

    let body: unknown
    try {
      body = await response.json()
    } catch {
      throw new ApiClientError(
        '服务响应不是有效 JSON。',
        'contract',
        response.status
      )
    }

    if (!response.ok) {
      const parsedError = errorSchema.safeParse(body)
      if (!parsedError.success)
        throw new ApiClientError(
          '服务错误响应不符合接口契约。',
          'contract',
          response.status
        )
      throw new ApiClientError(
        parsedError.data.error.message,
        'service',
        response.status,
        parsedError.data.error.code,
        parsedError.data.request_id,
        parsedError.data.error.fields
      )
    }

    const parsed = schema.safeParse(body)
    if (!parsed.success)
      throw new ApiClientError(
        '服务成功响应不符合接口契约。',
        'contract',
        response.status
      )
    return parsed.data
  }

  async function getBlob(path: string): Promise<Blob> {
    let response: Response
    try {
      response = await fetchApi(path, { cache: 'no-store' })
    } catch (error) {
      if (error instanceof TypeError)
        throw new ApiClientError('无法连接 AstroPhotoFlow 服务。', 'network')
      throw error
    }
    if (!response.ok) {
      let body: unknown
      try {
        body = await response.json()
      } catch {
        throw new ApiClientError(
          '服务响应不是有效 JSON。',
          'contract',
          response.status
        )
      }
      const parsedError = errorSchema.safeParse(body)
      if (!parsedError.success)
        throw new ApiClientError(
          '服务错误响应不符合接口契约。',
          'contract',
          response.status
        )
      throw new ApiClientError(
        parsedError.data.error.message,
        'service',
        response.status,
        parsedError.data.error.code,
        parsedError.data.request_id,
        parsedError.data.error.fields
      )
    }
    if (!response.headers.get('Content-Type')?.startsWith('image/jpeg')) {
      throw new ApiClientError(
        '预览响应类型不符合接口契约。',
        'contract',
        response.status
      )
    }
    return response.blob()
  }

  return {
    get: <T>(path: string, schema: ZodType<T>) => request(path, schema),
    getBlob,
    upload,
    send: <T>(
      path: string,
      schema: ZodType<T>,
      method: 'POST' | 'PATCH' | 'DELETE',
      data: unknown
    ) =>
      request(path, schema, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
  }
}

export interface WorkbenchClient {
  selectDirectory(path: string): Promise<string | null>
  getConfiguration(): Promise<ConfigState>
  saveConfiguration(body: ConfigSave): Promise<ConfigState>
  restart(operationId: string): Promise<WorkbenchResult>
  restartResult(operationId: string): Promise<WorkbenchResult | null>
}

export function createWorkbenchClient(fetchApi: FetchApi): WorkbenchClient {
  const client = createApiClient(fetchApi)
  const path = '/astrophotoflow/api/v1/settings/workbench'
  return {
    selectDirectory: async (directory) => {
      const result = await client.send(path + '/select-directory', directorySelectionSchema, 'POST', { path: directory })
      return result.path
    },
    getConfiguration: () => client.get(path, configStateSchema),
    saveConfiguration: (body) =>
      client.send(path, configStateSchema, 'PATCH', body),
    restart: (operationId) =>
      client.send(path + '/restart', workbenchResultSchema, 'POST', {
        operation_id: operationId
      }),
    restartResult: (operationId) =>
      client.get(
        path + '/restart/' + operationId,
        workbenchResultSchema.nullable()
      )
  }
}
