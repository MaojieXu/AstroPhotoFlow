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
})
