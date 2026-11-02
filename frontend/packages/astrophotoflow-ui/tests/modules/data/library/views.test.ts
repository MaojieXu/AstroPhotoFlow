import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import type { QueryClient } from '@tanstack/vue-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useLibraryView } from '@ui/modules/data/library/useLibraryView'
import type { LibraryViewInput } from '@ui/modules/data/library/useLibraryView'
import { useDatasetMembersView } from '@ui/modules/data/datasets/useDatasetMembersView'
import { useRecordSearch } from '@ui/modules/data/workspace/useRecordSearch'
import { libraryQueryKey } from '@ui/modules/data/library/queries'

const { search, members } = vi.hoisted(() => ({
  search: vi.fn(),
  members: vi.fn()
}))
vi.mock('@ui/modules/data/api/index', () => ({
  libraryApi: { search, members },
  catalogApi: {}
}))
let wrapper: ReturnType<typeof mount> | undefined
beforeEach(() => {
  search
    .mockReset()
    .mockImplementation(async (query) => ({
      items: [],
      total: 0,
      limit: query.limit,
      offset: query.offset
    }))
  members.mockReset()
})
afterEach(() => {
  wrapper?.unmount()
  vi.useRealTimers()
})
function openLibrary() {
  const input = ref<LibraryViewInput>({
    workspaceId: '/one',
    active: true,
    pageSize: 50,
    offset: 0,
    search: '',
    category: 'all',
    filters: {},
    sort: { by: 'created_at', order: 'desc' }
  })
  const paused = ref(false)
  let view!: ReturnType<typeof useLibraryView>, cache!: QueryClient
  wrapper = mount(
    defineComponent({
      setup() {
        view = useLibraryView(input, paused)
        cache = useQueryClient()
        return () => null
      }
    })
  )
  return {
    input,
    paused,
    get view() {
      return view
    },
    get cache() {
      return cache
    }
  }
}

it('holds query parameters during an edit and resumes only the latest parameter scope after invalidation', async () => {
  const { input, paused, view, cache } = openLibrary()
  await flushPromises()
  paused.value = true
  input.value = { ...input.value, search: 'pending selection' }
  await flushPromises()
  await cache.invalidateQueries({ queryKey: libraryQueryKey('/one') })
  expect(search).toHaveBeenCalledTimes(1)
  expect(view.request.value?.query.q).toBeUndefined()
  paused.value = false
  await flushPromises()
  expect(search).toHaveBeenCalledTimes(2)
  expect(search.mock.calls[1][0].q).toBe('pending selection')
  expect(view.request.value?.query.q).toBe('pending selection')
})

it('returns to a fresh original library scope without another HTTP read', async () => {
  const { input, view } = openLibrary()
  await flushPromises()
  input.value = { ...input.value, active: false }
  await flushPromises()
  expect(view.request.value).toBeUndefined()
  expect(view.query.data.value).toBeUndefined()
  input.value = { ...input.value, active: true }
  await flushPromises()
  expect(search).toHaveBeenCalledTimes(1)
  expect(view.query.data.value?.items).toEqual([])
})

it('cancels fixed member reads and never carries member data across a new fixed version while paused', async () => {
  const input = ref({
    workspaceId: '/one',
    active: true,
    pageSize: 50,
    offset: 0,
    search: '',
    dataset: { id: 'dataset-a', versionId: 'fixed-a' },
    sort: { by: 'member_position', order: 'asc' as const }
  })
  const paused = ref(false)
  let finish!: (value: unknown) => void,
    view!: ReturnType<typeof useDatasetMembersView>
  members
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        })
    )
    .mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 })
  wrapper = mount(
    defineComponent({
      setup() {
        view = useDatasetMembersView(input, paused)
        return () => null
      }
    })
  )
  await flushPromises()
  const signal = members.mock.calls[0][3] as AbortSignal
  paused.value = true
  input.value = {
    ...input.value,
    dataset: { id: 'dataset-b', versionId: 'fixed-b' }
  }
  await flushPromises()
  expect(signal.aborted).toBe(true)
  expect(view.request.value?.versionId).toBe('fixed-b')
  finish({ items: [], total: 0, limit: 50, offset: 0 })
  await flushPromises()
  expect(view.query.data.value).toBeUndefined()
  paused.value = false
  await flushPromises()
  expect(members).toHaveBeenCalledTimes(2)
  expect(members.mock.calls[1].slice(0, 3)).toEqual([
    'dataset-b',
    'fixed-b',
    expect.objectContaining({ sort_by: 'position', offset: 0 })
  ])
})

it('debounces rapid typing while navigation immediately uses its current search', async () => {
  vi.useFakeTimers()
  const text = ref(''),
    scope = ref('library')
  let state!: ReturnType<typeof useRecordSearch>
  wrapper = mount(
    defineComponent({
      setup() {
        state = useRecordSearch(text, scope)
        return () => null
      }
    })
  )
  text.value = 'old'
  await flushPromises()
  await vi.advanceTimersByTimeAsync(200)
  text.value = 'latest'
  await flushPromises()
  await vi.advanceTimersByTimeAsync(249)
  expect(state.query.value).toBe('')
  expect(state.pending.value).toBe(true)
  await vi.advanceTimersByTimeAsync(1)
  expect(state.query.value).toBe('latest')
  text.value = 'project search'
  scope.value = 'projects'
  await flushPromises()
  expect(state.query.value).toBe('project search')
  expect(state.pending.value).toBe(false)
})
