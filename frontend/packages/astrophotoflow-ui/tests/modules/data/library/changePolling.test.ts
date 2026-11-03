import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import { VueQueryPlugin } from '@tanstack/vue-query'
import { afterEach, expect, it, vi } from 'vitest'
import { createPlatformQueryClient } from '@ui/core/query/client'
import { useLibraryQuery } from '@ui/modules/data/library/queries'
import { invalidateLibraryData } from '@ui/modules/data/library/invalidation'

const api = vi.hoisted(() => ({ search: vi.fn(), changeState: vi.fn() }))
vi.mock('@ui/modules/data/api', () => ({ libraryApi: api, catalogApi: {} }))
afterEach(() => { vi.useRealTimers(); vi.clearAllMocks() })

it('polls the small change state and reloads the page only when it changes', async () => {
  vi.useFakeTimers()
  api.changeState.mockResolvedValue({revision_token:'one',thumbnail_token:'ready'})
  api.search.mockResolvedValue({items:[],total:0,limit:50,offset:0})
  const cache = createPlatformQueryClient()
  const request = ref({workspaceId:'workspace',query:{limit:50,offset:0},all:false,empty:false})
  const wrapper = mount(defineComponent({setup(){useLibraryQuery(request,false);return()=>null}}),
    {global:{plugins:[[VueQueryPlugin,{queryClient:cache}]]}})
  try {
    await flushPromises()
    expect(api.search).toHaveBeenCalledOnce()
    await vi.advanceTimersByTimeAsync(10_000)
    await flushPromises()
    expect(api.changeState).toHaveBeenCalledTimes(2)
    expect(api.search).toHaveBeenCalledOnce()
    api.changeState.mockResolvedValue({revision_token:'two',thumbnail_token:'ready'})
    await vi.advanceTimersByTimeAsync(10_000)
    await flushPromises()
    expect(api.search).toHaveBeenCalledTimes(2)
  } finally { wrapper.unmount(); cache.clear() }
})

it('invalidates the edited asset and its cached groups without invalidating unrelated groups or workspaces', async () => {
  const cache = createPlatformQueryClient()
  const related = ['workspace','one','datasets','related','versions','v1','members']
  const unrelated = ['workspace','one','datasets','other','versions','v2','members']
  const foreign = ['workspace','two','datasets','related','versions','v1','members']
  cache.setQueryData(related,{items:[{id:'edited'}]})
  cache.setQueryData(unrelated,{items:[{id:'different'}]})
  cache.setQueryData(foreign,{items:[{id:'edited'}]})
  await invalidateLibraryData(cache,'one',{assetIds:['edited']})
  expect(cache.getQueryState(related)?.isInvalidated).toBe(true)
  expect(cache.getQueryState(unrelated)?.isInvalidated).toBe(false)
  expect(cache.getQueryState(foreign)?.isInvalidated).toBe(false)
  cache.clear()
})
