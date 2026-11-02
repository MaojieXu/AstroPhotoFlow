import { describe, expect, it, vi } from 'vitest'
import { createSoftwareClient } from '@ui/modules/software/api/client'
import type { SoftwareCommand } from '@ui/modules/software/api/contracts'

describe('Bundle command reference', () => {
  it('retains arbitrary assessment data for the requested package version', async () => {
    const commands: SoftwareCommand[] = [{
      command: 'render', scriptable: true, syntax: 'render source',
      description: 'Fixture command.', url: 'https://example.invalid/commands/render',
      assessment: { note: 'Bundle-owned evidence', flags: ['unchecked'], score: 0 }
    }]
    const fetchApi = vi.fn().mockResolvedValue(new Response(JSON.stringify(commands), { status: 200 }))
    const result = await createSoftwareClient(fetchApi).listCommands('sample-tool', '7.8.9')
    expect(result).toEqual(commands)
    expect(fetchApi.mock.calls[0][0]).toContain('/sample-tool/versions/7.8.9/commands')
  })
})
