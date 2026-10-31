import { fromPartial } from '@total-typescript/shoehorn'
import { render, screen, waitFor } from '@testing-library/vue'
import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import { LGraph, LGraphNode } from '@/lib/litegraph/src/litegraph'
import type { ComponentWidget } from '@/scripts/domWidget'

import BundleResultWidget from './BundleResultWidget.vue'

const f = vi.hoisted(() => ({ result: vi.fn(), state: vi.fn() }))
vi.mock('@/stores/nodeOutputStore', () => ({ useNodeOutputStore: () => ({ getNodeOutputs: f.result }) }))
vi.mock('./useAutomaticResults', () => ({ automaticResultState: f.state, setAutomaticResult: vi.fn(), retryAutomaticResult: vi.fn() }))
vi.mock('vue-i18n', async (original) => ({ ...await original<typeof import('vue-i18n')>(), useI18n: () => ({ t: (key: string) => key }) }))

describe('complete result ownership', () => {
  it('retains the old result as stale and rejects other workflows and late signatures', async () => {
    const graph = new LGraph()
    const node = new LGraphNode('Process')
    graph.add(node)
    const automatic = ref({ signature: 'old', submitted: 'old', phase: 'completed' })
    const result = (prompt: string, signature: string, workflow = graph.id) => ({ prompt_id: prompt,
      call_id: '00000000-0000-4000-8000-000000000004', node_id: String(node.id), workflow_id: workflow,
      state: 'completed', calculation_signature: signature, ports: [] })
    const oldId = '11111111-1111-4111-8111-111111111111'
    const newId = '22222222-2222-4222-8222-222222222222'
    const output = ref({ apf_result: [result(oldId, 'old')] })
    f.result.mockImplementation(() => output.value)
    f.state.mockImplementation(() => automatic.value)
    const view = render(BundleResultWidget, { props: { widget: fromPartial<ComponentWidget<string | object>>({ node }) } })
    expect(screen.getByText(/11111111/)).toBeInTheDocument()
    automatic.value = { signature: 'new', submitted: 'new', phase: 'running' }
    await screen.findByText('astrophotoflow.results.previousResult')
    output.value = { apf_result: [result(newId, 'new', '33333333-3333-4333-8333-333333333333')] }
    await waitFor(() => expect(screen.queryByText(/22222222/)).not.toBeInTheDocument())
    output.value = { apf_result: [result(newId, 'new')] }
    await screen.findByText(/22222222/)
    output.value = { apf_result: [result(oldId, 'old')] }
    await waitFor(() => expect(screen.queryByText(/11111111/)).not.toBeInTheDocument())
    expect(screen.getByText(/22222222/)).toBeInTheDocument()
    view.unmount()
  })
})
