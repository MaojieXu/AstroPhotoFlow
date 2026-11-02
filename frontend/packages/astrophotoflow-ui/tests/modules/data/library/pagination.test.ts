import { describe, expect, it, vi } from 'vitest'
import { readPages } from '@ui/modules/data/library/pagination'

describe('explicit all-mode paging', () => {
  it('preserves server order across every page, including a short final page', async () => {
    const read = vi.fn()
      .mockResolvedValueOnce({ items: [4, 0], offset: 0, limit: 2, total: 5 })
      .mockResolvedValueOnce({ items: [3, 1], offset: 2, limit: 2, total: 5 })
      .mockResolvedValueOnce({ items: [2], offset: 4, limit: 2, total: 5 })
    const result = await readPages(read, true, new AbortController().signal)
    expect(result.items).toEqual([4, 0, 3, 1, 2])
    expect(read.mock.calls).toEqual([[], [2], [4]])
  })

  it('keeps an ordinary requested page rather than resetting its offset', async () => {
    const page = { items: [50], offset: 50, limit: 1, total: 100 }
    const read = vi.fn().mockResolvedValue(page)
    await expect(readPages(read, false, new AbortController().signal)).resolves.toBe(page)
    expect(read).toHaveBeenCalledExactlyOnceWith()
  })

  it('rejects a failed later page instead of returning the first page as complete', async () => {
    const failure = new Error('The second page failed')
    const read = vi.fn().mockResolvedValueOnce({ items: [0, 1], offset: 0, limit: 2, total: 3 })
      .mockRejectedValueOnce(failure)
    await expect(readPages(read, true, new AbortController().signal)).rejects.toBe(failure)
    expect(read.mock.calls).toEqual([[], [2]])
  })

  it('rejects late final bytes when the transport does not honor cancellation', async () => {
    const controller = new AbortController()
    const finalPage = { items: [2], offset: 2, limit: 2, total: 3 }
    let finish!: (page: typeof finalPage) => void
    let started!: () => void
    const secondPage = new Promise<void>(resolve => { started = resolve })
    const read = vi.fn().mockResolvedValueOnce({ items: [0, 1], offset: 0, limit: 2, total: 3 })
      .mockImplementationOnce(() => { started(); return new Promise(resolve => { finish = resolve }) })
    const pending = readPages(read, true, controller.signal)
    await secondPage
    controller.abort()
    finish(finalPage)
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
  })
})
