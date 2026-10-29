import { describe, expect, it, vi } from 'vitest'
import { createSirilPreviewClient } from '@ui/modules/software/api/preview'
import type { SirilPreviewRequest } from '@ui/modules/software/api/preview'

const body: SirilPreviewRequest = {
  reference: { kind: 'asset_version', asset_version_id: '00000000-0000-4000-8000-000000000001', selection: { kind: 'whole_file' } },
  consumer_id: '00000000-0000-4000-8000-000000000002', generation: 1,
  member_index: 0, linked: false, shadowsclip: 0, targetbg: 0
}

describe('Siril display preview client', () => {
  it('passes fixed references, zero values and abort signal without modifying them', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('png', { headers: { 'Content-Type': 'image/png' } }))
    const signal = new AbortController().signal
    const result = await createSirilPreviewClient(fetch).render(body, signal)
    expect(result.type).toBe('image/png')
    const [path, init] = fetch.mock.calls[0]
    expect(path).toBe('/astrophotoflow/api/v1/software/packages/siril/autostretch-preview')
    expect(init.signal).toBe(signal)
    expect(JSON.parse(init.body)).toEqual(body)
  })

  it('reports missing software as an actionable error', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'SOFTWARE_NOT_READY', message: 'Install Siril first' } }), { status: 503 }))
    await expect(createSirilPreviewClient(fetch).render(body, new AbortController().signal)).rejects.toMatchObject({ code: 'SOFTWARE_NOT_READY', status: 503 })
  })
})
