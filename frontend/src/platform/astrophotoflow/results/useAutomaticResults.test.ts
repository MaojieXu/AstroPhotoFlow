import type { NodeCapability } from '@astrophotoflow/ui'
import { fromPartial } from '@total-typescript/shoehorn'
import { render } from '@testing-library/vue'
import { defineComponent, reactive } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { LGraph, LGraphNode } from '@/lib/litegraph/src/litegraph'
import type { ComfyApiWorkflow, ComfyWorkflowJSON } from '@/platform/workflow/validation/schemas/workflowSchema'
import { api } from '@/scripts/api'
import type { ComfyApp, QueuePromptOptions } from '@/types/comfy'

import { bundleCapabilities } from '../sidebar/bundleCatalog'
import { automaticResultStates, useAutomaticResults } from './automatic'

const stores = vi.hoisted(() => ({ app: vi.fn(), workflow: vi.fn(), execution: vi.fn(), queue: vi.fn() }))
vi.mock('@/scripts/appInstance', () => ({ useApp: stores.app }))
vi.mock('@/platform/workflow/management/stores/workflowStore', () => ({ useWorkflowStore: stores.workflow }))
vi.mock('@/stores/executionStore', () => ({ useExecutionStore: stores.execution }))
vi.mock('@/stores/queueStore', () => ({ useQueuePendingTaskCountStore: stores.queue }))

function setup() {
  vi.useFakeTimers()
  vi.spyOn(api, 'getQueue').mockResolvedValue({ Running: [], Pending: [fromPartial({ id: 'automatic-prompt' })] })
  vi.spyOn(api, 'fetchApi').mockResolvedValue(new Response('{}'))
  const graph = new LGraph()
  const source = new LGraphNode('Source')
  const node = new LGraphNode('Process')
  node.comfyClass = 'APF_auto_test'
  graph.add(source)
  graph.add(node)
  const sourceId = String(source.id), id = String(node.id)
  const prompt: ComfyApiWorkflow = {
    [sourceId]: { class_type: 'APF_DATA_REFERENCE', inputs: { reference: 'fixed-reference' } },
    [id]: { class_type: 'APF_auto_test', inputs: { image: [sourceId, 0], strength: 0 } }
  }
  bundleCapabilities.set('APF_auto_test', fromPartial<NodeCapability>({ automatic_result_preview: true, available: true,
    node: { content_token: 'v1', definition: { execution: { inputs: { image: 'image' } } } }, operation: { inputs: [{ name: 'image', required: true }] } }))
  const workflow = reactive({ activeWorkflow: { path: 'Unsaved Workflow.json' } })
  stores.workflow.mockReturnValue(workflow)
  stores.execution.mockReturnValue(reactive({ isIdle: true }))
  stores.queue.mockReturnValue(reactive({ count: 0 }))
  const queuePrompt = vi.fn(async (_number: number, _count?: number, options?: QueuePromptOptions | string[]) => {
    if (!options || Array.isArray(options) || !options.automaticResult) return false
    if (!await options.automaticResult.isCurrent(prompt)) return false
    options.automaticResult.queued('automatic-prompt')
    return true
  })
  const context = { graph, prompt }
  const app = fromPartial<ComfyApp>({ get rootGraph() { return context.graph }, isGraphReady: true, graphToPrompt: async () => ({ workflow: fromPartial<ComfyWorkflowJSON>({ id: context.graph.id, version: .4, nodes: [] }), output: context.prompt }), queuePrompt })
  stores.app.mockReturnValue(app)
  const view = render(defineComponent({ setup() { useAutomaticResults(); return () => null } }))
  return { ...view, prompt, id, graph, queuePrompt, app, workflow, context }
}

afterEach(() => { automaticResultStates.clear(); bundleCapabilities.clear(); vi.useRealTimers(); vi.restoreAllMocks() })

describe('automatic native result scheduling', () => {
  it('queues both branch leaves once with their shared upstream in one prompt', async () => {
    const view = setup()
    const leaves: string[] = []
    for (const strength of [.2, .3]) {
      const node = new LGraphNode('Branch')
      node.comfyClass = 'APF_auto_test'
      view.graph.add(node)
      const id = String(node.id)
      leaves.push(id)
      view.prompt[id] = { class_type: 'APF_auto_test', inputs: { image: [view.id, 0], strength } }
    }
    await vi.advanceTimersByTimeAsync(500)
    await vi.waitFor(() => expect(view.queuePrompt).toHaveBeenCalledTimes(1))
    const options = view.queuePrompt.mock.calls[0]?.[2]
    expect(options && !Array.isArray(options) && options.automaticResult?.targets).toEqual(leaves)
    expect(options && !Array.isArray(options) && Object.keys(options.automaticResult?.signatures ?? {})).toHaveLength(4)
    view.unmount()
  })
  it('stops pending submissions for the old workflow after switching graphs', async () => {
    const view = setup()
    await vi.advanceTimersByTimeAsync(500)
    await vi.waitFor(() => expect(view.queuePrompt).toHaveBeenCalledTimes(1))
    view.prompt[view.id].inputs.strength = .8
    api.dispatchCustomEvent('graphChanged', null)
    const next = new LGraph()
    view.context.graph = next
    view.context.prompt = {}
    view.workflow.activeWorkflow = { path: 'Other draft.json' }
    api.dispatchCustomEvent('execution_success', { prompt_id: 'automatic-prompt', timestamp: 0 })
    await vi.advanceTimersByTimeAsync(1000)
    expect(view.queuePrompt).toHaveBeenCalledTimes(1)
    view.unmount()
  })
  it('debounces edits for 500 ms, runs unsaved drafts and ignores display-only events', async () => {
    const view = setup()
    await vi.advanceTimersByTimeAsync(499)
    expect(view.queuePrompt).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    await vi.waitFor(() => expect(view.queuePrompt).toHaveBeenCalledTimes(1))
    api.dispatchCustomEvent('execution_success', { prompt_id: 'automatic-prompt', timestamp: 0 })
    await vi.advanceTimersByTimeAsync(500)
    view.prompt[view.id]._meta = { title: 'Custom title' }
    api.dispatchCustomEvent('graphChanged', null)
    await vi.advanceTimersByTimeAsync(500)
    expect(view.queuePrompt).toHaveBeenCalledTimes(1)
    view.unmount()
  })

  it('finishes the current run and collapses edits to the latest parameters', async () => {
    const view = setup()
    await vi.advanceTimersByTimeAsync(500)
    await vi.waitFor(() => expect(view.queuePrompt).toHaveBeenCalledTimes(1))
    for (const strength of [.2, .4, .6]) {
      view.prompt[view.id].inputs.strength = strength
      api.dispatchCustomEvent('graphChanged', null)
      await vi.advanceTimersByTimeAsync(500)
    }
    expect(view.queuePrompt).toHaveBeenCalledTimes(1)
    api.dispatchCustomEvent('execution_success', { prompt_id: 'automatic-prompt', timestamp: 0 })
    await vi.advanceTimersByTimeAsync(500)
    await vi.waitFor(() => expect(view.queuePrompt).toHaveBeenCalledTimes(2))
    expect(automaticResultStates.get(`${view.graph.id}:${view.id}`)?.submitted).toBe(automaticResultStates.get(`${view.graph.id}:${view.id}`)?.signature)
    view.unmount()
  })

  it('does not loop after failure without a new input revision', async () => {
    const view = setup()
    await vi.advanceTimersByTimeAsync(500)
    await vi.waitFor(() => expect(view.queuePrompt).toHaveBeenCalledTimes(1))
    api.dispatchCustomEvent('execution_error', { prompt_id: 'automatic-prompt', timestamp: 0, node_type: 'APF_auto_test', executed: [], exception_message: 'Actual failure', exception_type: 'RuntimeError', traceback: [] })
    await vi.advanceTimersByTimeAsync(2000)
    api.dispatchCustomEvent('graphChanged', null)
    await vi.advanceTimersByTimeAsync(500)
    expect(view.queuePrompt).toHaveBeenCalledTimes(1)
    expect(automaticResultStates.get(`${view.graph.id}:${view.id}`)?.phase).toBe('failed')
    view.unmount()
  })
})


it('marks a submission without a prompt receipt failed even when the host returns true', async () => {
  const view = setup()
  view.queuePrompt.mockImplementationOnce(async () => true)
  await vi.advanceTimersByTimeAsync(1000)
  await vi.waitFor(() => expect(automaticResultStates.get(`${view.graph.id}:${view.id}`)?.phase).toBe('failed'))
  api.dispatchCustomEvent('graphChanged', null)
  await vi.advanceTimersByTimeAsync(1000)
  expect(view.queuePrompt).toHaveBeenCalledTimes(1)
  view.unmount()
})

it('releases a deleted queued prompt after native status, without looping or treating query errors as deletion', async () => {
  const view = setup()
  await vi.advanceTimersByTimeAsync(500)
  await vi.waitFor(() => expect(view.queuePrompt).toHaveBeenCalledTimes(1))
  vi.mocked(api.getQueue).mockRejectedValueOnce(new Error('offline'))
  api.dispatchCustomEvent('status', null)
  await vi.advanceTimersByTimeAsync(500)
  await vi.waitFor(() => expect(api.getQueue).toHaveBeenCalledTimes(1))
  expect(automaticResultStates.get(`${view.graph.id}:${view.id}`)?.phase).toBe('queued')
  vi.mocked(api.getQueue).mockResolvedValue({ Running: [], Pending: [] })
  api.dispatchCustomEvent('status', null)
  await vi.advanceTimersByTimeAsync(1500)
  await vi.waitFor(() => expect(automaticResultStates.get(`${view.graph.id}:${view.id}`)?.phase).toBe('failed'))
  expect(view.queuePrompt).toHaveBeenCalledTimes(1)
  view.prompt[view.id].inputs.strength = .7
  api.dispatchCustomEvent('graphChanged', null)
  await vi.advanceTimersByTimeAsync(500)
  await vi.waitFor(() => expect(view.queuePrompt).toHaveBeenCalledTimes(2))
  view.unmount()
})


it('keeps success when execution finishes before the host queue refresh resolves', async () => {
  const view = setup()
  view.queuePrompt.mockImplementationOnce(async (_number, _count, options) => {
    if (!options || Array.isArray(options) || !options.automaticResult) return false
    options.automaticResult.queued('automatic-prompt')
    api.dispatchCustomEvent('execution_success', { prompt_id: 'automatic-prompt', timestamp: 0 })
    await Promise.resolve()
    return true
  })
  await vi.advanceTimersByTimeAsync(1000)
  await vi.waitFor(() => expect(view.queuePrompt).toHaveBeenCalledTimes(1))
  expect(automaticResultStates.get(`${view.graph.id}:${view.id}`)?.phase).toBe('completed')
  view.unmount()
})


it('allows connected Data science without requiring a second library reference', async () => {
  const view = setup()
  const source = Object.keys(view.prompt).find(id => id !== view.id)!
  const data = new LGraphNode('Forward science')
  data.comfyClass = 'APF_DATA_REFERENCE'
  view.graph.add(data)
  const id = String(data.id)
  view.prompt[id] = { class_type: 'APF_DATA_REFERENCE', inputs: { science: [source, 0], reference: '' } }
  view.prompt[view.id].inputs.image = [id, 0]
  await vi.advanceTimersByTimeAsync(1000)
  await vi.waitFor(() => expect(view.queuePrompt).toHaveBeenCalledTimes(1))
  const options = view.queuePrompt.mock.calls[0]?.[2]
  expect(options && !Array.isArray(options) && options.automaticResult?.targets).toEqual([view.id])
  view.unmount()
})
