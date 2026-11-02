import { fromPartial } from '@total-typescript/shoehorn'
import { render, screen, waitFor } from '@testing-library/vue'
import { ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { LGraph, LGraphNode } from '@/lib/litegraph/src/litegraph'
import type { ComponentWidget } from '@/scripts/domWidget'

import BundleResultWidget from './BundleResultWidget.vue'
import type { SoftwareCallResult } from '@astrophotoflow/ui'
import { PlatformQueryPlugin } from '@astrophotoflow/ui'
vi.mock('../useNativeWorkspace')
import { nativeWorkspace } from '../__mocks__/useNativeWorkspace'
afterEach(() => {
  nativeWorkspace.workspaceId.value = '/test-workspace'
  nativeWorkspace.ready.value = true
})

const f = vi.hoisted(() => ({
  result: vi.fn(),
  state: vi.fn(),
  get: vi.fn(),
  analysis: vi.fn()
}))
vi.mock(import('@astrophotoflow/ui'), async (original) => ({
  ...(await original()),
  createRunResultClient: () => ({ get: f.get, analysis: f.analysis })
}))
vi.mock('@/stores/nodeOutputStore', () => ({
  useNodeOutputStore: () => ({ getNodeOutputs: f.result })
}))
vi.mock('./automatic', () => ({
  automaticResultState: f.state,
  setAutomaticResult: vi.fn(),
  retryAutomaticResult: vi.fn()
}))
vi.mock('vue-i18n', async (original) => ({
  ...(await original<typeof import('vue-i18n')>()),
  useI18n: () => ({ t: (key: string) => key })
}))

describe('complete result ownership', () => {
  it('retains the old result as stale and rejects other workflows and late signatures', async () => {
    const graph = new LGraph()
    const node = new LGraphNode('Process')
    graph.add(node)
    const automatic = ref({
      signature: 'old',
      submitted: 'old',
      phase: 'completed'
    })
    const result = (
      prompt: string,
      signature: string,
      workflow = graph.id
    ): SoftwareCallResult => ({log_url: `/astrophotoflow/api/v1/runs/${prompt}/calls/${'00000000-0000-4000-8000-000000000004'}/log`, 
      prompt_id: prompt,
      call_id: '00000000-0000-4000-8000-000000000004',
      node_id: String(node.id),
      workflow_id: workflow,
      state: 'completed',
      calculation_signature: signature,
      ports: [],
      package_id: null,
      software_version: null,
      bundle_version: null,
      bundle_commit: null,
      development_source: null,
      operation_id: null,
      definition_token: null,
      preview_error: null,
      observation: null,
      error: null
    })
    f.get.mockImplementation(async (identity: { prompt_id: string }) => ({
      ...result(
        identity.prompt_id,
        identity.prompt_id === oldId ? 'old' : 'new'
      )
    }))
    const oldId = '11111111-1111-4111-8111-111111111111'
    const newId = '22222222-2222-4222-8222-222222222222'
    const output = ref({ apf_result: [result(oldId, 'old')] })
    f.result.mockImplementation(() => output.value)
    f.state.mockImplementation(() => automatic.value)
    const view = render(BundleResultWidget, {
      props: {
        widget: fromPartial<ComponentWidget<string | object>>({ node })
      },
      global: { plugins: [PlatformQueryPlugin] }
    })
    await waitFor(() => expect(f.get).toHaveBeenCalled())
    expect(await screen.findByText(/11111111/)).toBeInTheDocument()
    automatic.value = { signature: 'new', submitted: 'new', phase: 'running' }
    await screen.findByText('astrophotoflow.results.previousResult')
    output.value = {
      apf_result: [result(newId, 'new', '33333333-3333-4333-8333-333333333333')]
    }
    await waitFor(() =>
      expect(screen.queryByText(/22222222/)).not.toBeInTheDocument()
    )
    output.value = { apf_result: [result(newId, 'new')] }
    await screen.findByText(/22222222/)
    output.value = { apf_result: [result(oldId, 'old')] }
    await waitFor(() =>
      expect(screen.queryByText(/11111111/)).not.toBeInTheDocument()
    )
    expect(screen.getByText(/22222222/)).toBeInTheDocument()
    nativeWorkspace.workspaceId.value = undefined
    nativeWorkspace.ready.value = false
    await waitFor(() =>
      expect(screen.queryByText(/22222222/)).not.toBeInTheDocument()
    )
    nativeWorkspace.workspaceId.value = '/test-workspace'
    nativeWorkspace.ready.value = true
    expect(await screen.findByText(/22222222/)).toBeInTheDocument()
    view.unmount()
  })
})

it('uses the checked member and log URLs from the response without reconstructing routes',async()=>{
 const graph=new LGraph(),node=new LGraphNode('File result');graph.add(node)
 const record:SoftwareCallResult={prompt_id:'11111111-1111-4111-8111-111111111111',call_id:'22222222-2222-4222-8222-222222222222',
  node_id:String(node.id),workflow_id:graph.id,log_url:'/opaque/call-log',calculation_signature:'fixed',package_id:'siril',software_version:'1.4.4',
  bundle_version:null,bundle_commit:null,development_source:null,operation_id:null,definition_token:null,state:'completed',preview_error:null,observation:null,error:null,
  ports:[{name:'report',type:'APF_FILE',members:[{name:'report.txt',format:'other',view_base:'/opaque/member-view',file_url:'/opaque/download'}]}]}
 f.get.mockResolvedValue(record);f.result.mockReturnValue({apf_result:[record]});f.state.mockReturnValue({signature:'fixed',submitted:'fixed',phase:'completed'})
 const view=render(BundleResultWidget,{props:{widget:fromPartial<ComponentWidget<string|object>>({node})},global:{plugins:[PlatformQueryPlugin]}})
 await waitFor(()=>expect(screen.getByRole('link',{name:'astrophotoflow.results.fullFile'})).toHaveAttribute('href','/opaque/download'))
 expect(view.container.querySelector('a[href="/opaque/call-log"]')).not.toBeNull()
 expect(screen.getByText('report.txt')).toBeVisible()
 view.unmount()
})
