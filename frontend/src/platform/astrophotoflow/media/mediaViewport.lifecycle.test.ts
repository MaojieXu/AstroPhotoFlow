import OpenSeadragon from 'openseadragon'
import { fromPartial } from '@total-typescript/shoehorn'
import { expect, it, vi } from 'vitest'
import type { MediaState } from '@astrophotoflow/ui'
import { createImageViewport, BROWSER_TILE_LIMIT } from './viewport'
const engine = vi.hoisted(() => ({
  create: vi.fn(),
  destroy: vi.fn(),
  addHandler: vi.fn()
}))
vi.mock('openseadragon', async (original) => {
  const actual = await original<{ default: typeof OpenSeadragon }>()
  return { ...actual, default: Object.assign(engine.create, actual.default) }
})
it('uses the returned tile descriptor, bounds browser resources and delegates destruction to the native viewer', () => {
  engine.create.mockReturnValue(
    fromPartial<OpenSeadragon.Viewer>({
      destroy: engine.destroy,
      addHandler: engine.addHandler
    })
  )
  const failed = vi.fn(),
    element = document.createElement('div')
  const image = fromPartial<MediaState>({
    width: 6000,
    height: 4000,
    max_level: 13,
    tile_size: 256,
    tile_url: '/fixed/version/tiles/{level}/{x}/{y}'
  })
  const viewport = createImageViewport(element, image, {
    failed,
    zoom: vi.fn(),
    bounds: vi.fn()
  })
  const options = engine.create.mock.calls[0]![0]
  expect(options).toMatchObject({
    element,
    maxImageCacheCount: BROWSER_TILE_LIMIT,
    imageLoaderLimit: 4,
    tileRetryMax: 0
  })
  expect(options.tileSources[0].getTileWidth(0)).toBe(256)
  expect(options.tileSources[0].getTileUrl(0, 0, 0)).toBe(
    '/fixed/version/tiles/0/0/0'
  )
  const handler = engine.addHandler.mock.calls.find(
    (call) => call[0] === 'tile-load-failed'
  )?.[1]
  expect(handler).toBeDefined()
  handler()
  expect(failed).toHaveBeenCalledOnce()
  viewport.destroy()
  expect(engine.destroy).toHaveBeenCalledOnce()
})
