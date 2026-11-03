import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import LibraryThumbnail from '@ui/modules/data/library/LibraryThumbnail.vue'

describe('library thumbnail cells', () => {
  it('updates only the cell whose cached image becomes available', async () => {
    const urls = reactive<Record<string, string>>({})
    const firstRead = vi.fn(() => urls.first)
    const secondRead = vi.fn(() => urls.second)
    const first = mount(LibraryThumbnail, { props: { read: firstRead } })
    const second = mount(LibraryThumbnail, { props: { read: secondRead } })
    const initialSecondReads = secondRead.mock.calls.length
    urls.first = 'blob:first'
    await flushPromises()
    expect(first.get('img').attributes('src')).toBe('blob:first')
    expect(second.find('img').exists()).toBe(false)
    expect(secondRead).toHaveBeenCalledTimes(initialSecondReads)
    first.unmount()
    second.unmount()
  })
})
