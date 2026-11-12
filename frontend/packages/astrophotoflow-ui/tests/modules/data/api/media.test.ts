import { expect, it, vi } from 'vitest'

import { createMediaClient, mediaStateSchema } from '@ui/modules/data/api/media'

it('uses the supplied member URL and preserves omitted, null and zero display settings', async () => {
  const state = mediaStateSchema.parse({
    key: 'view',
    status: 'generating',
    phase: 'queued',
    kind: 'image',
    width: 0,
    height: 0,
    max_level: 0,
    tile_size: 512,
    selection: {},
    arrays: [],
    hdus: [],
    needs_selection: false,
    overview_url: null,
    tile_url: null,
    video_url: null,
    mime_type: null,
    proxy: false,
    frame_index: null,
    media_time: null,
    frame_count: null,
    duration: null,
    note: null,
    display_recipe: null,
    error: null
  })
  const fetch = vi.fn().mockResolvedValue(Response.json(state))
  const selection = {
    hdu_index: 0,
    frame_index: null,
    preview_max_edge: 512
  } as const
  expect(
    await createMediaClient(fetch).prepare('/server/member', selection)
  ).toEqual(state)
  expect(fetch.mock.calls[0][0]).toBe('/server/member/viewer')
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(selection)
})

it('reports invalid media responses instead of returning a previous viewer state', async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json({}))
  await expect(
    createMediaClient(fetch).status('/server/member', 'view')
  ).rejects.toMatchObject({ kind: 'contract', status: 200 })
  expect(fetch).toHaveBeenCalledTimes(1)
})

it('forwards cancellation to preview reads, and releases only the display consumer', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response('pixels', {headers:{'Content-Type':'image/png'}}))
  const client = createMediaClient(fetch)
  const controller = new AbortController()
  const image = await client.image('/overview', controller.signal)
  expect(await image.text()).toBe('pixels')
  const signal = fetch.mock.calls[0]![1].signal as AbortSignal
  controller.abort()
  expect(signal.aborted).toBe(true)
  fetch.mockResolvedValueOnce(new Response(null, { status: 204 }))
  await client.release('/member', 'consumer / one')
  expect(fetch.mock.calls[1]![0]).toBe(
    '/member/viewer/consumer/consumer%20%2F%20one'
  )
  expect(fetch.mock.calls[1]![1]).toMatchObject({
    method: 'DELETE',
    keepalive: true
  })
})
