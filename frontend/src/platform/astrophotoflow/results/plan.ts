import type { ComfyApiWorkflow } from '@/platform/workflow/validation/schemas/workflowSchema'

export type AutomaticNodePolicy = {
  allowed: boolean
  enabled: boolean
  available: boolean
  identity: unknown
  required: string[]
}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`
  if (value && typeof value === 'object') return `{${Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => `${JSON.stringify(key)}:${canonical(item)}`).join(',')}}`
  return JSON.stringify(value) ?? 'null'
}

export async function contentSignature(value: unknown): Promise<string> {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonical(value)))
  return Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, '0')).join('')
}

export async function automaticResultPlan(prompt: ComfyApiWorkflow, policies: Record<string, AutomaticNodePolicy>) {
  const signatures: Record<string, string> = {}
  const blocked: Record<string, 'manual' | 'unavailable' | 'input' | 'cycle'> = {}
  const ancestors: Record<string, Set<string>> = {}
  const visiting = new Set<string>()
  const visited = new Set<string>()
  async function visit(id: string): Promise<void> {
    if (visited.has(id)) return
    if (visiting.has(id)) { blocked[id] = 'cycle'; return }
    visiting.add(id)
    const node = prompt[id]
    const policy = policies[id]
    ancestors[id] = new Set()
    if (!policy?.allowed) blocked[id] = 'manual'
    else if (!policy.available) blocked[id] = 'unavailable'
    else if (policy.required.some(name => node.inputs[name] === undefined || node.inputs[name] === null || node.inputs[name] === '')) blocked[id] = 'input'
    const inputs: Record<string, unknown> = {}
    for (const [name, value] of Object.entries(node.inputs)) {
      if (Array.isArray(value) && value.length === 2 && typeof value[0] === 'string' && prompt[value[0]]) {
        const parent = value[0]
        await visit(parent)
        ancestors[id].add(parent)
        for (const ancestor of ancestors[parent] ?? []) ancestors[id].add(ancestor)
        if (blocked[parent]) blocked[id] ??= blocked[parent]
        inputs[name] = [parent, value[1], signatures[parent]]
      } else inputs[name] = value
    }
    signatures[id] = await contentSignature([node.class_type, inputs, policy?.identity])
    visiting.delete(id)
    visited.add(id)
  }
  for (const id of Object.keys(prompt)) await visit(id)
  const eligible = Object.keys(prompt).filter(id => policies[id]?.enabled && policies[id]?.allowed && !blocked[id])
  return { signatures, blocked, ancestors, eligible }
}
