import { mount,flushPromises } from '@vue/test-utils'
import { defineComponent,h } from 'vue'
import { expect,it,vi } from 'vitest'
import { useLibraryBootstrap } from '@ui/modules/data/library/queries'
const {health,capabilities}=vi.hoisted(()=>({health:vi.fn(),capabilities:vi.fn()}))
vi.mock('@ui/modules/data/api',()=>({catalogApi:{health,capabilities},libraryApi:{}}))

it('cancels both initial reads when their last page closes',async()=>{
  let finishHealth!: (value:unknown)=>void,finishCapabilities!: (value:unknown)=>void
  health.mockImplementationOnce(()=>new Promise(resolve=>{finishHealth=resolve}))
  capabilities.mockImplementationOnce(()=>new Promise(resolve=>{finishCapabilities=resolve}))
  let query!:ReturnType<typeof useLibraryBootstrap>
  const wrapper=mount(defineComponent({setup(){query=useLibraryBootstrap();return ()=>h('div')}}))
  await flushPromises()
  const healthSignal=health.mock.calls[0][0] as AbortSignal
  const capabilitySignal=capabilities.mock.calls[0][0] as AbortSignal
  wrapper.unmount()
  expect(healthSignal.aborted).toBe(true)
  expect(capabilitySignal.aborted).toBe(true)
  finishHealth({workspace:'/closed'});finishCapabilities({asset_import:true});await flushPromises()
  expect(query.data.value).toBeUndefined()
})
