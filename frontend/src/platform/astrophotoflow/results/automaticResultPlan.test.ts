import { describe, expect, it } from 'vitest'

import type { ComfyApiWorkflow } from '@/platform/workflow/validation/schemas/workflowSchema'

import { automaticResultPlan } from './plan'
import type { AutomaticNodePolicy } from './plan'

const policy: AutomaticNodePolicy = { allowed: true, enabled: true, available: true, identity: ['definition', 'fingerprint'], required: [] }

describe('automatic complete-result dependency plan', () => {
  it('changes only affected branch signatures and includes shared dependencies', async () => {
    const prompt: ComfyApiWorkflow = {
      '1': { class_type: 'APF_DATA_REFERENCE', inputs: { reference: 'fixed-source' } },
      '2': { class_type: 'processing', inputs: { image: ['1', 0], strength: 0 } },
      '3': { class_type: 'processing', inputs: { image: ['2', 0] } },
      '4': { class_type: 'processing', inputs: { image: ['1', 0] } }
    }
    const policies = Object.fromEntries(Object.keys(prompt).map(id => [id, policy]))
    const before = await automaticResultPlan(prompt, policies)
    prompt['2'].inputs.strength = .5
    const after = await automaticResultPlan(prompt, policies)
    expect(after.signatures['1']).toBe(before.signatures['1'])
    expect(after.signatures['4']).toBe(before.signatures['4'])
    expect(after.signatures['2']).not.toBe(before.signatures['2'])
    expect(after.signatures['3']).not.toBe(before.signatures['3'])
    expect(after.ancestors['3']).toEqual(new Set(['2', '1']))
    prompt['3']._meta = { title: 'User title' }
    expect((await automaticResultPlan(prompt, policies)).signatures).toEqual(after.signatures)
    policies['2'] = { ...policy, identity: ['definition', 'new-helper-content'] }
    expect((await automaticResultPlan(prompt, policies)).signatures['3']).not.toBe(after.signatures['3'])
  })

  it.each(['manual', 'unavailable', 'input'] as const)('blocks a complete chain with %s upstream', async reason => {
    const prompt: ComfyApiWorkflow = {
      '1': { class_type: 'upstream', inputs: {} },
      '2': { class_type: 'processing', inputs: { image: ['1', 0] } }
    }
    const blocked = { ...policy, allowed: reason !== 'manual', available: reason !== 'unavailable', required: reason === 'input' ? ['reference'] : [] }
    const result = await automaticResultPlan(prompt, { '1': blocked, '2': policy })
    expect(result.blocked['2']).toBe(reason)
    expect(result.eligible).toEqual([])
  })

  it('rejects cyclic dependencies without executing either node', async () => {
    const prompt: ComfyApiWorkflow = { '1': { class_type: 'process', inputs: { image: ['2', 0] } }, '2': { class_type: 'process', inputs: { image: ['1', 0] } } }
    const result = await automaticResultPlan(prompt, { '1': policy, '2': policy })
    expect(result.eligible).toEqual([])
  })
})
