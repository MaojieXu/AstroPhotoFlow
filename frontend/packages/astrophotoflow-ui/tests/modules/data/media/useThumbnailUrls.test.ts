import { effectScope } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useThumbnailUrls } from '@ui/modules/data/media/useThumbnailUrls'

let scope = effectScope()
const createUrl = vi.fn<(blob: Blob) => string>()
const revokeUrl = vi.fn<(url: string) => void>()

beforeEach(() => {
  scope = effectScope()
  createUrl.mockReset().mockImplementation(() => `blob:${createUrl.mock.calls.length}`)
  revokeUrl.mockReset()
  vi.stubGlobal('URL', class extends URL {
    static createObjectURL = createUrl
    static revokeObjectURL = revokeUrl
  })
})
afterEach(() => {
  scope.stop()
  vi.unstubAllGlobals()
})

describe('view-owned thumbnail resources', () => {
  it('moves newly visible rows ahead of offscreen queued rows', async () => {
    const finishes = new Map<string, (blob: Blob) => void>()
    const read = vi.fn<(id: string, signal: AbortSignal) => Promise<Blob>>()
      .mockImplementation(id => new Promise(resolve => { finishes.set(id, resolve) }))
    const thumbnails = scope.run(() => useThumbnailUrls(id => id, read))!
    const loading = thumbnails.load(['one','two','three','four','five','six'])
    thumbnails.prioritize(['six'])
    finishes.get('one')!(new Blob(['one']))
    await Promise.resolve(); await Promise.resolve()
    expect(read.mock.calls[4][0]).toBe('six')
    finishes.get('two')!(new Blob(['two']))
    await Promise.resolve(); await Promise.resolve()
    for (const id of ['three','four','five','six']) finishes.get(id)!(new Blob([id]))
    await loading
    expect(Object.keys(thumbnails.urls.value)).toHaveLength(6)
  })

  it('keeps in-flight requests when the same page refreshes and bounds concurrency', async () => {
    const finishes = new Map<string, (blob: Blob) => void>()
    const read = vi.fn<(id: string, signal: AbortSignal) => Promise<Blob>>()
      .mockImplementation(id => new Promise(resolve => { finishes.set(id, resolve) }))
    const thumbnails = scope.run(() => useThumbnailUrls(id => id, read))!
    const page = ['a', 'b', 'c', 'd', 'e']
    const first = thumbnails.load(page)
    const second = thumbnails.load([...page])
    expect(read).toHaveBeenCalledTimes(4)
    expect(read.mock.calls.every(([, signal]) => !signal.aborted)).toBe(true)
    finishes.get('a')!(new Blob(['a']))
    await Promise.resolve()
    await Promise.resolve()
    expect(read).toHaveBeenCalledTimes(5)
    for (const id of page.slice(1)) finishes.get(id)!(new Blob([id]))
    await Promise.all([first, second])
    expect(Object.keys(thumbnails.urls.value).sort()).toEqual(page)
    expect(revokeUrl).not.toHaveBeenCalled()
  })

  it('keeps a fresh shared-version refresh when an older page read arrives later',async()=>{
    let finishOld!: (blob:Blob)=>void
    const read=vi.fn<(id:string,signal:AbortSignal)=>Promise<Blob>>()
      .mockImplementationOnce(()=>new Promise(resolve=>{finishOld=resolve}))
      .mockResolvedValue(new Blob(['fresh']))
    const thumbnails=scope.run(()=>useThumbnailUrls(id=>id,read))!
    const loading=thumbnails.load(['position-one'])
    await thumbnails.refresh('position-one',['position-one','position-two'])
    expect(read).toHaveBeenCalledTimes(2)
    expect(Object.keys(thumbnails.urls.value)).toEqual(['position-one','position-two'])
    const fresh={...thumbnails.urls.value}
    finishOld(new Blob(['older']));await loading
    expect(thumbnails.urls.value).toEqual(fresh)
    expect(createUrl).toHaveBeenCalledTimes(2)
    scope.stop()
    expect(revokeUrl).toHaveBeenCalledTimes(2)
  })

  it('cancels an old page and ignores its late bytes after the new page is ready', async () => {
    let finishOld!: (blob: Blob) => void
    const read = vi.fn<(id: string, signal: AbortSignal) => Promise<Blob>>()
      .mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve }))
      .mockResolvedValue(new Blob(['new page']))
    const thumbnails = scope.run(() => useThumbnailUrls(id => id, read))!
    const oldLoad = thumbnails.load(['old'])
    const oldSignal = read.mock.calls[0][1]
    await thumbnails.load(['new'])
    expect(oldSignal.aborted).toBe(true)
    expect(thumbnails.urls.value).toEqual({ new: 'blob:1' })
    finishOld(new Blob(['old page']))
    await oldLoad
    expect(thumbnails.urls.value).toEqual({ new: 'blob:1' })
    expect(createUrl).toHaveBeenCalledTimes(1)
  })

  it('releases every replaced URL and every URL left when the view closes', async () => {
    const read = vi.fn().mockResolvedValue(new Blob(['thumbnail']))
    const thumbnails = scope.run(() => useThumbnailUrls((id: string) => id, read))!
    await thumbnails.load(['one', 'two'])
    await thumbnails.load(['three'])
    expect(revokeUrl.mock.calls).toEqual([['blob:1'], ['blob:2']])
    scope.stop()
    expect(revokeUrl.mock.calls).toEqual([['blob:1'], ['blob:2'], ['blob:3']])
    expect(thumbnails.urls.value).toEqual({})
  })

  it('aborts pending work on disposal without creating an unreachable object URL', async () => {
    let finish!: (blob: Blob) => void
    const read = vi.fn<(id: string, signal: AbortSignal) => Promise<Blob>>()
      .mockImplementation(() => new Promise(resolve => { finish = resolve }))
    const thumbnails = scope.run(() => useThumbnailUrls(id => id, read))!
    const pending = thumbnails.load(['one'])
    scope.stop()
    expect(read.mock.calls[0][1].aborted).toBe(true)
    finish(new Blob(['late']))
    await pending
    expect(createUrl).not.toHaveBeenCalled()
  })

  it('retries only missing thumbnails while keeping completed rows visible', async () => {
    const read = vi.fn<(id: string, signal: AbortSignal) => Promise<Blob>>()
      .mockImplementationOnce(async () => new Blob(['ready']))
      .mockRejectedValueOnce(new Error('not ready'))
      .mockImplementationOnce(async () => new Blob(['generated']))
    const thumbnails = scope.run(() => useThumbnailUrls(id => id, read))!
    await thumbnails.load(['one', 'two'])
    const first = thumbnails.urls.value.one
    expect(first).toBeDefined()
    expect(thumbnails.urls.value.two).toBeUndefined()
    await thumbnails.loadMissing(['one', 'two'])
    expect(thumbnails.urls.value.one).toBe(first)
    expect(thumbnails.urls.value.two).toBeDefined()
    expect(read.mock.calls.map(([id]) => id)).toEqual(['one', 'two', 'two'])
    expect(revokeUrl).not.toHaveBeenCalled()
  })
})
