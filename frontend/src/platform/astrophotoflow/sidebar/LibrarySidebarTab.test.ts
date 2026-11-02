import userEvent from '@testing-library/user-event'
import { render, screen } from '@testing-library/vue'
import { createPinia } from 'pinia'
import { nextTick } from 'vue'
import { api } from '@/scripts/api'
import { describe, expect, it, vi } from 'vitest'

import { useToast } from '@/components/ui/toast/toastStore'

import LibrarySidebarTab from './LibrarySidebarTab.vue'

const {showIssue}=vi.hoisted(()=>({showIssue:vi.fn()}))
vi.mock('../canvas/dataBridge',()=>({addLibraryDataToCanvas:vi.fn()}))

vi.mock('@/platform/settings/composables/useSettingsDialog',()=>({useSettingsDialog:()=>({show:vi.fn()})}))

vi.mock('@astrophotoflow/ui', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@astrophotoflow/ui')>()
  const { defineComponent } = await import('vue')
  return {
    ...actual,
    Workspace: defineComponent({
      props: {connectionEpoch:{type:Number,default:0},connected:{type:Boolean,default:true}},
      emits: ['notify-success','notify-import','workspace-changed'],
      setup(_props,{expose}){expose({showImportIssue:showIssue})},
      template: `<div data-testid="workspace-connection" :data-epoch="connectionEpoch" :data-connected="connected"><button @click="$emit('notify-success', 'M31：导入完成')">Complete import</button><button @click="$emit('notify-import',{kind:'warning',taskId:'task',category:'content',title:'Partial failure',description:'1 failed'})">Partial failure</button><button @click="$emit('workspace-changed','/new')">Workspace changed</button></div>`
    })
  }
})

vi.mock('@/stores/workspace/sidebarTabStore', () => ({
  useSidebarTabStore: () => ({ sidebarTabs: [{ id: 'library', canClose: undefined }] })
}))

describe('library notification bridge', () => {
  it('delivers an import success to the native toast with a finite duration', async () => {
    const pinia = createPinia()
    const user = userEvent.setup()
    const { unmount } = render(LibrarySidebarTab, {
      global: {
        plugins: [pinia],
        mocks: { $t: (key: string) => key },
        stubs: { SidebarTabTemplate: { template: '<div><slot name="body" /></div>' } }
      }
    })
    await user.click(screen.getByRole('button', { name: 'Complete import' }))
    expect(useToast(pinia).toasts).toEqual([
      expect.objectContaining({ kind: 'success', title: 'M31：导入完成', duration: 4000 })
    ])
    await user.click(screen.getByRole('button',{name:'Partial failure'}))
    const warning=useToast(pinia).toasts.find(item=>item.kind==='warning')
    expect(warning).toEqual(expect.objectContaining({title:'Partial failure',description:'1 failed',closable:true,duration:Infinity}))
    warning?.action?.onClick()
    expect(showIssue).toHaveBeenCalledWith('task','content')
    expect(screen.getByTestId('workspace-connection').getAttribute('data-epoch')).toBe('0')
    api.dispatchCustomEvent('reconnecting')
    await nextTick()
    expect(screen.getByTestId('workspace-connection').getAttribute('data-connected')).toBe('false')
    api.dispatchCustomEvent('reconnected')
    await nextTick()
    expect(screen.getByTestId('workspace-connection').getAttribute('data-epoch')).toBe('1')
    expect(screen.getByTestId('workspace-connection').getAttribute('data-connected')).toBe('true')
    await user.click(screen.getByRole('button',{name:'Workspace changed'}))
    expect(useToast(pinia).toasts).toHaveLength(0)
    unmount()
    expect(useToast(pinia).toasts).toHaveLength(0)
  })
})
