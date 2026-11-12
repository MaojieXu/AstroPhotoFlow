import { describe, expect, it, vi } from 'vitest'

import { createPlatformClient } from '@ui/core/api/client'
import {
  getWorkspaceLocaleApiV1SettingsLocaleGet,
  restartWorkbenchApiV1SettingsWorkbenchRestartPost
} from '@ui/generated/api/sdk.gen'
import { zConfigSave, zWorkspaceLocale } from '@ui/generated/api/zod.gen'
import { createNodeClient } from '@ui/modules/nodes/client'

const locale = getWorkspaceLocaleApiV1SettingsLocaleGet<true>

describe('generated platform client', () => {
  it('keeps workspace instances separate and validates the generated response', async () => {
    const firstFetch = vi
      .fn()
      .mockResolvedValue(Response.json({ locale: 'zh' }))
    const secondFetch = vi
      .fn()
      .mockResolvedValue(Response.json({ locale: 'en' }))
    const first = createPlatformClient({
      fetchApi: firstFetch,
      baseUrl: new URL('/first', window.location.origin).href
    })
    const second = createPlatformClient({
      fetchApi: secondFetch,
      baseUrl: new URL('/second', window.location.origin).href
    })
    expect((await locale({ client: first, throwOnError: true })).data).toEqual({
      locale: 'zh'
    })
    expect((await locale({ client: second, throwOnError: true })).data).toEqual(
      { locale: 'en' }
    )
    expect(firstFetch.mock.calls[0][0]).toBe('/first/api/v1/settings/locale')
    expect(secondFetch.mock.calls[0][0]).toBe('/second/api/v1/settings/locale')
    expect(
      zWorkspaceLocale.safeParse({ locale: 'zh', invented: true }).success
    ).toBe(false)
  })

  it.each([{ locale: 'invalid' }, { locale: 'zh', invented: true }])(
    'rejects a successful body outside the generated contract: %o',
    async (body) => {
      const client = createPlatformClient({
        fetchApi: vi.fn().mockResolvedValue(Response.json(body))
      })
      await expect(
        locale({ client, throwOnError: true })
      ).rejects.toMatchObject({ kind: 'contract', status: 200 })
    }
  )

  it('preserves service error diagnostics', async () => {
    const error = {
      error: {
        code: 'REVISION_CONFLICT',
        message: 'changed',
        fields: [{ path: 'revision', message: 'stale' }]
      },
      request_id: 'ce88796a-b7bb-488d-9f15-645d04a87be5'
    }
    const client = createPlatformClient({
      fetchApi: vi.fn().mockResolvedValue(Response.json(error, { status: 409 }))
    })
    await expect(locale({ client, throwOnError: true })).rejects.toMatchObject({
      kind: 'service',
      status: 409,
      code: error.error.code,
      requestId: error.request_id,
      fields: error.error.fields
    })
  })

  it('classifies network failure without fabricating an HTTP status', async () => {
    const fetchApi = vi.fn().mockRejectedValue(new TypeError('offline'))
    const client = createPlatformClient({ fetchApi })
    await expect(locale({ client, throwOnError: true })).rejects.toMatchObject({
      kind: 'network',
      status: undefined
    })
    expect(fetchApi).toHaveBeenCalledTimes(1)
  })

  it('reports malformed JSON as a contract failure', async () => {
    const client = createPlatformClient({
      fetchApi: vi.fn().mockResolvedValue(new Response('invalid-json'))
    })
    await expect(locale({ client, throwOnError: true })).rejects.toMatchObject({
      kind: 'contract',
      status: 200
    })
  })

  it('rejects invalid request data before sending a write', async () => {
    const fetchApi = vi.fn()
    const client = createPlatformClient({ fetchApi })
    await expect(
      restartWorkbenchApiV1SettingsWorkbenchRestartPost<true>({
        client,
        throwOnError: true,
        body: { operation_id: 'invalid-id' }
      })
    ).rejects.toMatchObject({ kind: 'contract' })
    expect(fetchApi).not.toHaveBeenCalled()
  })

  it.each([
    [undefined, true],
    [null, false],
    ['', false],
    ['C:/workspace', true]
  ])(
    'preserves default workspace omission and explicit value rules: %s',
    (value, valid) => {
      expect(zConfigSave.shape.default_workspace.safeParse(value).success).toBe(
        valid
      )
    }
  )

  it('uses the generated node directory and rejects an invalid identity before transport', async () => {
    const fetchApi = vi.fn().mockResolvedValue(Response.json([]))
    const client = createNodeClient(fetchApi)
    expect(await client.list()).toEqual([])
    expect(fetchApi.mock.calls[0][0]).toBe('/astrophotoflow/api/v1/nodes')
    await expect(client.get('invalid-id')).rejects.toMatchObject({
      kind: 'contract'
    })
    expect(fetchApi).toHaveBeenCalledTimes(1)
  })

  it('cancels the real read without retrying or converting cancellation to failure', async () => {
    let announceStarted: (() => void) | undefined
    const started = new Promise<void>((resolve) => {
      announceStarted = resolve
    })
    const fetchApi = vi.fn(
      (_path: string, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener(
            'abort',
            () => reject(new DOMException('Aborted', 'AbortError')),
            { once: true }
          )
          announceStarted?.()
        })
    )
    const client = createPlatformClient({ fetchApi })
    const controller = new AbortController()
    const pending = locale({
      client,
      throwOnError: true,
      signal: controller.signal
    })
    const rejected = expect(pending).rejects.toMatchObject({
      name: 'AbortError'
    })
    await started
    controller.abort()
    await rejected
    expect(fetchApi).toHaveBeenCalledTimes(1)
    expect(fetchApi.mock.calls[0][1]?.signal?.aborted).toBe(true)
  })
})

it('calls an injected native fetch as a function, preserving its receiver requirements',async()=>{
 function nativeFetch(this:unknown,_path:string,_init?:RequestInit):Promise<Response>{
  if(this!==undefined)throw new TypeError('Illegal invocation')
  return Promise.resolve(Response.json([]))
 }
 await expect(createNodeClient(nativeFetch).list()).resolves.toEqual([])
})
