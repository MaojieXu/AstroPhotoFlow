import { describe, expect, it, vi } from 'vitest'
import { createSoftwareClient } from '@ui/modules/software/api/client'
import type { SirilCommand } from '@ui/modules/software/api/contracts'

const assessment = (
  securityRisk: string,
  runtimeStatus: string,
  overrides: Partial<SirilCommand['assessment']> = {}
): SirilCommand['assessment'] => ({
  parameter_details: 'Source-derived parameter details.',
  structured_parameter_defaults_ranges: 'Ranges are unknown unless documented.',
  single_image_sequence_context: 'Single-image command; sequence behavior is not verified.',
  input_output_semantics: 'Changes the loaded image; save is separate.',
  headless_status: 'not_individually_verified',
  dependencies: 'unknown',
  security_risk: securityRisk,
  semantic_review_status: 'partial_official_description_only',
  node_definition_status: 'not_generated',
  node_definition_reason: 'No safe definition has been generated.',
  node_generation_status: 'not_generated',
  node_generation_reason: 'This row is catalog-only.',
  registry_load_status: 'not_applicable_no_node_definition',
  registry_load_reason: 'No definition exists to load.',
  runtime_test_status: runtimeStatus,
  runtime_test_reason: 'No real CLI run was recorded.',
  ...overrides
})

const commandList: SirilCommand[] = [
  {
    command: 'autostretch',
    scriptable: true,
    syntax: 'autostretch [-linked]',
    description: 'Stretch the image.',
    url: 'https://siril.readthedocs.io/en/stable/Commands.html#autostretch',
    assessment: assessment(
      'Alters the current image in memory; save is separate.',
      'success_single_file_and_forced_stop_observed',
      {
        node_definition_status: 'candidate_definition_available',
        node_generation_status: 'candidate_definition_available',
        registry_load_status: 'unknown_not_checked_in_real_comfyui_registry',
        registry_load_reason: 'No real ComfyUI registry observation was captured.'
      }
    )
  },
  {
    command: 'addmax',
    scriptable: false,
    syntax: 'addmax filename',
    description: 'Combine with maximum values.',
    url: 'https://siril.readthedocs.io/en/stable/Commands.html#addmax',
    assessment: assessment('Reads a caller-selected image; path behavior is unknown.', 'not_tested')
  },
  {
    command: 'pyscript',
    scriptable: true,
    syntax: 'pyscript scriptname.py [script_argv]',
    description: 'Executes a Siril Python script.',
    url: 'https://siril.readthedocs.io/en/stable/Commands.html#pyscript',
    assessment: assessment('High risk: executes caller-selected arbitrary Python; no generic node is generated.', 'not_tested')
  }
]

describe('Version-bound command catalog', () => {
  it('retains assessment and unknown evidence when removed from the package page', async () => {
    const fetchApi = vi.fn().mockResolvedValue(new Response(JSON.stringify(commandList), { status: 200 }))
    const result = await createSoftwareClient(fetchApi).listCommands('siril', '1.4.4')
    expect(result).toEqual(commandList)
    expect(result.find(item => item.command === 'pyscript')?.assessment.security_risk).toContain('Python')
    expect(fetchApi.mock.calls[0][0]).toContain('/siril/versions/1.4.4/commands')
  })
})
