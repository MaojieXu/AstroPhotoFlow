import { render,waitFor } from '@testing-library/vue'
import { nextTick } from 'vue'
import { defineComponent,h,ref } from 'vue'
import { afterEach,expect,it,vi } from 'vitest'
import { PlatformQueryPlugin } from '@astrophotoflow/ui'
import { useNativeWorkspace } from './useNativeWorkspace'

const handlers=vi.hoisted(()=>new Map<string,EventListener>())
vi.mock('@/scripts/api',()=>({api:{addEventListener:(name:string,fn:EventListener)=>handlers.set(name,fn),removeEventListener:(name:string)=>handlers.delete(name)}}))
let wrapper:ReturnType<typeof render>|undefined
afterEach(()=>{wrapper?.unmount();wrapper=undefined;vi.restoreAllMocks()})

it('shares one verified connection, drops its workspace on disconnect and verifies the replacement before reuse',async()=>{
  let workspace='/one'
  const fetchSpy=vi.mocked(fetch).mockImplementation(async()=>Response.json({status:'ok',api_version:'v1',database:'ready',schema_revision:'0001',workspace}))
  let first!:ReturnType<typeof useNativeWorkspace>,second!:ReturnType<typeof useNativeWorkspace>
  const visible=ref(false)
  const Child=defineComponent({setup(){second=useNativeWorkspace();return()=>null}})
  wrapper=render(defineComponent({setup(){first=useNativeWorkspace();return()=>h('div',visible.value?[h(Child)]:[])}}),{global:{plugins:[PlatformQueryPlugin]}})
  await waitFor(()=>expect(first.workspaceId.value).toBe('/one'))
  const reads=fetchSpy.mock.calls.length
  visible.value=true;await waitFor(()=>expect(second?.workspaceId.value).toBe('/one'))
  expect(fetchSpy).toHaveBeenCalledTimes(reads)
  expect(handlers.size).toBe(2)
  handlers.get('reconnecting')!(new Event('reconnecting'));await nextTick()
  expect(first.workspaceId.value).toBeUndefined();expect(second.workspaceId.value).toBeUndefined()
  workspace='/two'
  handlers.get('reconnected')!(new Event('reconnected'));await waitFor(()=>expect(first.workspaceId.value).toBe('/two'))
  expect(first.workspaceId.value).toBe('/two');expect(second.workspaceId.value).toBe('/two')
  expect(fetchSpy).toHaveBeenCalledTimes(reads+1)
  visible.value=false;await nextTick();expect(handlers.size).toBe(2)
  wrapper.unmount();wrapper=undefined;expect(handlers.size).toBe(0)
})
