import { describe, expect, it, vi } from 'vitest'

import { createSoftwareClient } from '@ui/modules/software/api/client'

const command = {
  command: 'autostretch',
  scriptable: true,
  syntax: 'autostretch [-linked]',
  description: 'Auto-stretches the currently loaded image.',
  url: 'https://siril.readthedocs.io/en/stable/Commands.html#autostretch',
  assessment: {
    parameter_details: 'Parameters are documented.',
    structured_parameter_defaults_ranges: 'Unknown unless stated.',
    single_image_sequence_context: 'Current image.',
    input_output_semantics: 'In-memory transform; save is separate.',
    headless_status: 'observed_in_siril_1.4.4_cli_script',
    dependencies: 'None documented.',
    security_risk: 'Alters the current image in memory; save is separate.',
    semantic_review_status: 'partial_source_and_real_single_file_behavior',
    node_definition_status: 'candidate_definition_available',
    node_definition_reason: 'No additional definition reason recorded.',
    node_generation_status: 'candidate_definition_available',
    node_generation_reason: 'No additional generation reason recorded.',
    registry_load_status: 'unknown_not_checked_in_real_comfyui_registry',
    registry_load_reason: 'No real ComfyUI registry observation was captured.',
    runtime_test_status: 'success_single_file_and_forced_stop_observed',
    runtime_test_reason: 'Real baseline and three parameter rounds produced rereadable FITS; one OS-force-stop is not product cancellation.'
  }
}

describe('SoftwareClient', () => {
  it('reads commands from the exact package and version path', async () => {
    const fetchApi = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify([command]), { status: 200 })
      )
    const client = createSoftwareClient(fetchApi)

    await expect(client.listCommands('siril', '1.4.4')).resolves.toEqual([
      command
    ])
    expect(fetchApi).toHaveBeenCalledWith(
      '/astrophotoflow/api/v1/software/packages/siril/versions/1.4.4/commands',
      expect.objectContaining({ method: 'GET' })
    )
  })
})

it('forwards directory cancellation through the real generated Fetch transport',async()=>{
  const controller=new AbortController()
  let requestSignal:AbortSignal|undefined
  let finish!: (response:Response)=>void
  const fetchApi=vi.fn((_path:string,init?:RequestInit)=>{
    requestSignal=init?.signal??undefined
    return new Promise<Response>(resolve=>{finish=resolve})
  })
  const request=createSoftwareClient(fetchApi).listPackages(controller.signal)
  await new Promise(resolve=>setTimeout(resolve,0))
  expect(requestSignal?.aborted).toBe(false)
  controller.abort()
  expect(requestSignal?.aborted).toBe(true)
  finish(Response.json([]))
  await expect(request).resolves.toEqual([])
})
