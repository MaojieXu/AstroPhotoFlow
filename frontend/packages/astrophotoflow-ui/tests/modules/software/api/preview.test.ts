import { describe, expect, it, vi } from 'vitest'
import { createBundlePreviewClient } from '@ui/modules/software/api/preview'
import type { BundlePreviewRequest } from '@ui/modules/software/api/preview'

const body: BundlePreviewRequest = {
  reference: {
    kind: 'asset',
    asset_id: '00000000-0000-4000-8000-000000000001',
    selection: { kind: 'whole_file' }
  },
  consumer_id: '00000000-0000-4000-8000-000000000002',
  generation: 1,
  member_index: 0,
  package_id: 'siril',
  operation_id: 'autostretch',
  parameters: { linked: false, shadowsclip: 0, targetbg: 0 }
}

describe('Siril display preview client', () => {
  it('passes fixed references, zero values and abort signal without modifying them', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(
        new Response('png', { headers: { 'Content-Type': 'image/png' } })
      )
    const signal = new AbortController().signal
    const result = await createBundlePreviewClient(fetch).render(body, signal)
    expect(result.type).toBe('image/png')
    const [path, init] = fetch.mock.calls[0]
    expect(path).toBe('/astrophotoflow/api/v1/software/preview')
    expect(init.signal?.aborted).toBe(false)
    expect(JSON.parse(init.body)).toEqual(body)
  })

  it('reports missing software as an actionable error', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: 'SOFTWARE_NOT_READY',
              message: 'Install Siril first',
              fields: []
            },
            request_id: 'ce88796a-b7bb-488d-9f15-645d04a87be5'
          }),
          { status: 503 }
        )
      )
    await expect(
      createBundlePreviewClient(fetch).render(
        body,
        new AbortController().signal
      )
    ).rejects.toMatchObject({ code: 'SOFTWARE_NOT_READY', status: 503 })
  })

  it('rejects an unexpected successful media type', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(
        new Response('html', { headers: { 'Content-Type': 'text/html' } })
      )
    await expect(
      createBundlePreviewClient(fetch).render(
        body,
        new AbortController().signal
      )
    ).rejects.toMatchObject({ kind: 'contract', status: 200 })
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('keeps preview release alive during page teardown', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    await createBundlePreviewClient(fetch).release(body.consumer_id)
    expect(fetch).toHaveBeenCalledWith(
      `/astrophotoflow/api/v1/software/preview/${body.consumer_id}`,
      expect.objectContaining({ method: 'DELETE', keepalive: true })
    )
  })

  it('aborts the actual preview request without replay', async () => {
    let announceStarted: (() => void) | undefined
    const started = new Promise<void>((resolve) => {
      announceStarted = resolve
    })
    const fetch = vi.fn(
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
    const controller = new AbortController()
    const pending = createBundlePreviewClient(fetch).render(
      body,
      controller.signal
    )
    const rejected = expect(pending).rejects.toMatchObject({
      name: 'AbortError'
    })
    await started
    controller.abort()
    await rejected
    expect(fetch).toHaveBeenCalledTimes(1)
  })
})
